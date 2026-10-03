/* Creosote Labs — progressive enhancement only. The pages are complete without it.

   1. A skip link to <main>.
   2. Points the browser at favicon.svg when a page has no icon link.

   The navigation needs no script: three short items wrap onto a second row at
   narrow widths. */
(function () {
  "use strict";

  var doc = document;

  // ---- skip link -----------------------------------------------------------
  var main = doc.querySelector("main");
  if (main) {
    if (!main.id) main.id = "main";
    var skip = doc.createElement("a");
    skip.className = "skip";
    skip.href = "#" + main.id;
    skip.textContent = "Skip to content";
    doc.body.insertBefore(skip, doc.body.firstChild);
    main.setAttribute("tabindex", "-1");
  }

  // ---- favicon -------------------------------------------------------------
  if (!doc.querySelector('link[rel~="icon"]')) {
    var css = doc.querySelector('link[rel="stylesheet"][href$="styles.css"]');
    var icon = doc.createElement("link");
    icon.rel = "icon";
    icon.type = "image/svg+xml";
    icon.href = css ? css.getAttribute("href").replace(/styles\.css$/, "favicon.svg") : "/favicon.svg";
    doc.head.appendChild(icon);
  }
})();
