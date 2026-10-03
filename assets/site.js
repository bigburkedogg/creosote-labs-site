/* Creosote Labs — progressive enhancement only. The pages are complete without it.

   1. A skip link to <main>.
   2. Drops an eyebrow that only repeats the <h1> beneath it (build.py already
      leaves those out; this catches hand-made pages).
   3. Submits the contact form in place when it has a real endpoint, using the
      data-success / data-error text the template already carries.
   4. Points the browser at favicon.svg when a page has no icon link.

   The navigation needs no script: four short items wrap onto a second row at
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

  // ---- eyebrow that repeats the h1 ----------------------------------------
  Array.prototype.forEach.call(doc.querySelectorAll(".page-title .eyebrow"), function (el) {
    var h1 = el.parentNode && el.parentNode.querySelector("h1");
    if (!h1) return;
    var a = el.textContent.trim().toLowerCase();
    var b = h1.textContent.trim().toLowerCase();
    if (a && a === b) el.parentNode.removeChild(el);
  });

  // ---- contact form --------------------------------------------------------
  function statusNode(form) {
    var p = form.querySelector(".form-status");
    if (!p) {
      p = doc.createElement("p");
      p.className = "form-status";
      p.setAttribute("role", "status");
      p.setAttribute("aria-live", "polite");
      form.appendChild(p);
    }
    return p;
  }

  function say(form, text, state) {
    var p = statusNode(form);
    p.textContent = text || "";
    if (state) p.setAttribute("data-state", state);
    else p.removeAttribute("data-state");
  }

  Array.prototype.forEach.call(doc.querySelectorAll("form[data-success]"), function (form) {
    var action = form.getAttribute("action");
    // No endpoint, or no fetch: leave the browser's own behaviour alone.
    if (!action || !window.fetch || !window.FormData) return;

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var button = form.querySelector('button[type="submit"], button:not([type])');
      if (button) button.disabled = true;
      say(form, "Sending…");

      window.fetch(action, {
        method: (form.getAttribute("method") || "post").toUpperCase(),
        body: new FormData(form),
        headers: { Accept: "application/json" }
      }).then(function (res) {
        if (!res.ok) throw new Error(String(res.status));
        form.reset();
        say(form, form.getAttribute("data-success"), "ok");
        if (button) button.disabled = false;
      }).catch(function () {
        say(form, form.getAttribute("data-error"), "error");
        if (button) button.disabled = false;
      });
    });
  });
})();
