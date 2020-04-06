import json
import os

import requests
from flask import Flask, request, render_template, make_response, flash, redirect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_login.utils import _get_user, current_user
from flask_table import Table, Col
from pony.flask import Pony
from pony.orm import *
from sendgrid import SendGridAPIClient, To
from sendgrid.helpers.mail import Mail
from twilio.rest import Client

from RestaurantEmail import RestaurantEmail
from user_registration_form import UserRegistryForm
from utilities.credentials_hashing import hash_password, verify_password

# Create the application instance
app = Flask(__name__)
app.config.update(dict(
    DEBUG=False,
    SECRET_KEY='secret_xxx',
    PONY={
        'provider': 'mysql',
        'host': 'remotemysql.com', 'user': os.environ.get("DB_USER"),
        'passwd': os.environ.get("DB_PASS"), 'db': os.environ.get("DB_NAME")
    }
))

db = Database()


class User(db.Entity, UserMixin):
    login = Required(str, unique=True)
    username = Required(str)
    password = Required(str)
    phone = Required(str)
    is_active = Required(bool)


db.bind(**app.config['PONY'])
db.generate_mapping(create_tables=True)

login_manager = LoginManager(app)
login_manager.login_view = 'base_template'


@login_manager.user_loader
def load_user(user_id):
    return User.get(id=user_id)


Pony(app)


@app.before_request
def enforce_https_in_heroku():
    if request.headers.get('X-Forwarded-Proto') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        code = 301
        return redirect(url, code=code)


def send_welcome_sms(possible_user):
    account_sid = account_sid = os.environ.get("TWILIO_SID")
    auth_token = os.environ.get("TWILIO_TOKEN")
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body='Hi, ' + possible_user.username +
             ''' Welcome to the "whats-around-me" app. 
             
             Here you will be able to find restaurants around you, as you go. Just hit the button in the app's main page. 
             You will then receive an SMS with the opening hours and phone numbers of the 5 restaurants closer to your current location! 
             
             Enjoy!''',
        from_=os.environ.get("PHONE"),
        to=possible_user.phone
    )
    print(message.status)
    print(message.sid)


@db_session
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == '' or password == '':
            flash("Enter a name and password")
            return redirect('/')
        possible_user = User.get(login=email)
        if not possible_user:
            flash('Wrong username')
            return redirect('/')
        if verify_password(possible_user.password, password) and possible_user.is_active is True:
            print("Logged in")
            set_current_user(possible_user)
            login_user(possible_user)
            return redirect('/')
        flash('Wrong password or account not confirmed')
        return redirect('/')
    else:
        return render_template('base_template.html')


@db_session
@app.route('/userRegistry', methods=['GET', 'POST'])
def user_registry():
    form = UserRegistryForm()
    if form.validate_on_submit():
        if request.method == 'POST':
            email = request.form['email']
            password = hash_password(request.form['password'])
            name = request.form['name']
            phone = request.form['phone']
            exist = User.get(login=email)
            if exist:
                flash('The address %s is already in use, choose another one' % email)
                return redirect('/userRegistry')
            curr_user = User(login=email, username=name, password=password, phone=phone, is_active=False)
            commit()
            localhost_url = 'http://0.0.0.0:5000'
            message = Mail(
                from_email='olivbruno8@gmail.com',
                to_emails=To(email),
                subject='Confirm your account',
                html_content='<h2>Hello,<h2> to complete your registration click  <a href="' + (
                        os.environ.get("HEROKU_URL") or localhost_url) + '/activate/' + str(
                    curr_user.id) + '"> here </a>.'
            )
            try:
                sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
                response = sg.send(message)
                print(response.status_code)
                print(response.body)
                print(response.headers)
            except Exception as e:
                print(e.message)
            return redirect('/')
    else:
        return render_template('registry_form.html', title='Register', form=form)


@app.route('/activate/<id>', methods=['GET', 'POST'])
def activate(id):
    with db_session:
        user = User.get(id=id)
        if user:
            user.is_active = True
            commit()
            print("Logged in")
            send_welcome_sms(user)
            login_user(user)
            return redirect('/')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out')
    return redirect('/')


@app.route('/', methods=['GET', 'POST'])
def main_page():
    return render_template('locations_list.html')


@login_required
@app.route('/locations/<pos>', methods=['GET'])
def locations(pos):
    response = requests.get(
        "https://discover.search.hereapi.com/v1/discover?in=circle:" + pos + ";r=750&q=food&apiKey=" + os.environ.get(
            "HERE_API_KEY"))
    locationsJson = json.loads(response.text)

    class Locations(Table):
        name = Col('Name')
        address = Col('Address')
        site = Col('Website')

    items = []
    emailRestaurantInfo = []
    if locationsJson is not None:
        for loc in locationsJson['items']:
            restaurant_opening_hours = loc["openingHours"][0]["text"] if "openingHours" in loc else "N/A"
            is_open = loc["structured"]["isOpen"] if "structured" in loc and "isOpen" in loc["structured"] else "N/A"
            name = loc["title"]
            dist = loc["distance"]
            emailRestaurantInfo.append(RestaurantEmail(name, dist, restaurant_opening_hours, is_open))
            if "contacts" in loc and "www" in loc["contacts"][0]:
                items.append(dict(name=loc["title"], address=loc["address"]["label"],
                                  site=loc["contacts"][0]["www"][0]["value"]))
            else:
                items.append(dict(name=loc["title"], address=loc["address"]["label"], site=" - "))

    table = Locations(items)
    send_sms_with_restaurant_info(emailRestaurantInfo)

    return make_response(render_template("locations_list.html", table=table), 200)


@db_session
def send_sms_with_restaurant_info(emailRestaurantInfo):
    emailRestaurantInfo = sorted(emailRestaurantInfo, key=lambda k: k.distance)
    filtered = filter(lambda rest: rest.hours != "N/A", emailRestaurantInfo)
    messageBody = """
    The following nearby restaurants have the following opening hours:
    
    """

    for r in filtered[0:5]:
        messageBody += r.name + " - " + ",".join(r.hours) + " - located " + str(r.distance) + " meters away from current location."
        messageBody += """
        
        """

    account_sid = os.environ.get("TWILIO_SID")
    auth_token = os.environ.get("TWILIO_TOKEN")
    client = Client(account_sid, auth_token)
    message = client.messages.create(
    body=messageBody,
    from_=os.environ.get("PHONE"),
    to=current_user.phone
    )
    print(message.status)
    print(message.sid)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
