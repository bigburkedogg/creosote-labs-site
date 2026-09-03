(function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('nav');
  if (toggle && nav) {
    function close() { nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function (e) { if (e.target.closest('a')) close(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) { close(); toggle.focus(); }
    });
  }
  // Placeholder links (href="#") should not jump the page. Remove once they are filled.
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href="#"]');
    if (a) e.preventDefault();
  });
  // Works on the local server (training.html) and on clean-URL hosts (/training).
  var here = (location.pathname.split('/').pop() || 'index').replace(/\.html$/, '');
  document.querySelectorAll('.nav a').forEach(function (a) {
    var target = (a.getAttribute('href') || '').replace(/\.html$/, '');
    if (target === here) a.setAttribute('aria-current', 'page');
  });
})();
