/* Mobile navigation + footer year. No dependencies. */
(function () {
  "use strict";

  var header = document.getElementById("site-header");
  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("site-nav");
  if (!header || !toggle || !nav) return;

  var mq = window.matchMedia("(min-width: 960px)");
  var focusable = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function isOpen() {
    return toggle.getAttribute("aria-expanded") === "true";
  }

  function setOpen(open) {
    toggle.setAttribute("aria-expanded", String(open));
    header.classList.toggle("is-open", open);
    document.documentElement.classList.toggle("nav-open", open);
    if (open) {
      var first = nav.querySelector(focusable);
      if (first) first.focus();
    }
  }

  toggle.addEventListener("click", function () {
    setOpen(!isOpen());
  });

  document.addEventListener("keydown", function (e) {
    if (!isOpen()) return;
    if (e.key === "Escape") {
      setOpen(false);
      toggle.focus();
      return;
    }
    if (e.key === "Tab") {
      // Keep focus inside the open menu (toggle + nav) on small screens.
      var items = [toggle].concat(Array.prototype.slice.call(nav.querySelectorAll(focusable)));
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  document.addEventListener("click", function (e) {
    // Anything that is not the panel or its button closes the menu: the
    // backdrop (a pseudo-element, so its target is the header) included.
    if (isOpen() && !nav.contains(e.target) && !toggle.contains(e.target)) setOpen(false);
  });

  nav.addEventListener("click", function (e) {
    if (e.target.closest("a")) setOpen(false);
  });

  // Reset when the viewport grows into the desktop layout.
  var onChange = function (ev) { if (ev.matches && isOpen()) setOpen(false); };
  if (mq.addEventListener) mq.addEventListener("change", onChange);
  else mq.addListener(onChange);

  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());

  // --- email ------------------------------------------------------------
  // A mailto: link only does something when the device has a mail app set up.
  // On a desktop without one the click is a dead end, so the address is always
  // one click away from the clipboard, and the CTA reveals it after being used.

  // Older path, and the fallback when the Clipboard API refuses (no permission,
  // page not focused, insecure context).
  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:0;left:-9999px";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return legacyCopy(text) ? Promise.resolve() : Promise.reject();
      });
    }
    return legacyCopy(text) ? Promise.resolve() : Promise.reject();
  }

  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    var status = btn.parentNode.querySelector("[data-copy-status]");
    var timer;
    btn.addEventListener("click", function () {
      copyText(btn.dataset.copy).then(function () {
        btn.classList.add("is-done");
        if (status) status.textContent = "Correo copiado";
        clearTimeout(timer);
        timer = setTimeout(function () {
          btn.classList.remove("is-done");
          if (status) status.textContent = "";
        }, 2000);
      }).catch(function () {
        // Clipboard refused: select the text so it can be copied by hand.
        var range = document.createRange();
        range.selectNodeContents(btn.querySelector(".copy-inline__text") || btn);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      });
    });
  });
})();
