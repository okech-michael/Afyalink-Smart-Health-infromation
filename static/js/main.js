// AfyaLink — main.js

// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
  var alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity 0.4s';
      alert.style.opacity = '0';
      setTimeout(function () { alert.remove(); }, 400);
    }, 5000);
  });

  // Mark active nav link based on current URL path
  var currentPath = window.location.pathname;
  var navLinks = document.querySelectorAll('.nav-link');
  navLinks.forEach(function (link) {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });
});