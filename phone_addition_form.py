from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class PhoneAddition(FlaskForm):
    phone = StringField('Phone', validators=[DataRequired()])
    submit = SubmitField('Add')
