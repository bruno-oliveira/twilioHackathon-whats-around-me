
/* When the user clicks on the button,
toggle between hiding and showing the dropdown content */
function myFunction() {
  document.getElementById("myDropdown").classList.toggle("show");
    $('.topnav').css('overflow', 'visible')


}

// Close the dropdown menu if the user clicks outside of it
window.onclick = function(event) {
  if (!event.target.matches('.dropbtn')) {
    var dropdowns = document.getElementsByClassName("dropdown-content");
    var i;
    for (i = 0; i < dropdowns.length; i++) {
      var openDropdown = dropdowns[i];
      if (openDropdown.classList.contains('show')) {
        openDropdown.classList.remove('show');
      }
    }
  }
};

function fixNav(){
  $('.topnav').css('overflow', 'hidden');

  //document.getElementById("topNav").classList.toggle("fixnav");
}

function openDropdown() {
    document.getElementById("myDropdown").classList.toggle("show");
}

// Close the dropdown if the user clicks outside of it
window.onclick = function(e) {
    if (!e.target.matches('.dropbtn')) {
        var myDropdown = document.getElementById("myDropdown");
        if (myDropdown!== null && myDropdown.classList.contains('show')) {
            myDropdown.classList.remove('show');
        }
    }
}

var x = document.getElementById("pos");

function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(showPosition);
    } else {
        x.innerHTML = "Geolocation is not supported by this browser.";
    }
}

function showPosition(position) {
    var coords =  position.coords.latitude+","+position.coords.longitude
    $.ajax({
            type: 'GET',
            url: '/locations/' + coords
        }).then(function (result) {
         $('body').html(result);
        }, function (err) {
            console.log(err);
        });
}