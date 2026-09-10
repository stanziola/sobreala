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

  // --- theme ------------------------------------------------------------
  // The head script already set data-theme before the first paint. Here we only
  // handle switching it, remembering the choice, and the reveal animation.

  var themeBtn = document.getElementById("theme-toggle");
  var themeStatus = document.getElementById("theme-status");
  var themeMeta = document.getElementById("theme-color");
  var THEME_COLOR = { light: "#3166A7", dark: "#245285" };
  // The name of each mode, written by the build so the Spanish stays in
  // content.py. The row offers the other one; the status announces the one on.
  var themeLabel = themeBtn && themeBtn.querySelector("[data-theme-label]");
  var MODE = themeBtn
    ? { light: themeBtn.dataset.modeLight, dark: themeBtn.dataset.modeDark }
    : {};

  function currentTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function paintTheme(theme) {
    document.documentElement.dataset.theme = theme;
    if (themeMeta) themeMeta.setAttribute("content", THEME_COLOR[theme]);
    // The row says what pressing it will do, not what is on.
    if (themeLabel) themeLabel.textContent = theme === "dark" ? MODE.light : MODE.dark;
  }

  if (themeBtn) {
    // The build drew the light-mode row; the head script may have chosen dark.
    if (themeLabel && currentTheme() === "dark") themeLabel.textContent = MODE.light;

    themeBtn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      try { localStorage.setItem("theme", next); } catch (e) {}
      if (themeStatus) themeStatus.textContent = next === "dark" ? MODE.dark : MODE.light;

      var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (!document.startViewTransition || reduced) {
        paintTheme(next);
        return;
      }

      // Circular reveal growing from the button to the farthest corner.
      var r = themeBtn.getBoundingClientRect();
      var x = r.left + r.width / 2;
      var y = r.top + r.height / 2;
      var radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

      var transition = document.startViewTransition(function () { paintTheme(next); });
      transition.ready.then(function () {
        document.documentElement.animate(
          { clipPath: ["circle(0px at " + x + "px " + y + "px)",
                       "circle(" + radius + "px at " + x + "px " + y + "px)"] },
          { duration: 450, easing: "cubic-bezier(.2,.7,.2,1)",
            pseudoElement: "::view-transition-new(root)" }
        );
      }).catch(function () { /* the theme already changed; the animation is a bonus */ });
    });
  }

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

/* The account button. This site is static and lives on a different host than
   the panel, so it cannot know whether anyone is signed in: the session cookie
   is HttpOnly and SameSite=Lax, and neither travels here nor can be read.

   What can be read is the crumb the panel leaves on the parent domain when
   someone signs in: "1" for a client and "admin" for an administrator, and
   nothing else. A hint, not a proof — if the session was closed from another
   device this will keep offering "Mi panel" until someone presses it, and the
   panel will then ask them to sign in. That is the right order: what decides
   who gets in is the panel, not this line.

   El rol va ahí porque una cuenta de administrador no tiene panel de envíos ni
   contactos, y sin saberlo este menú ofrecía dos filas que no llevan a nada
   suyo. Cuesta que cualquier script de este dominio pueda saber que quien mira
   es administrador; no hay forma de que un sitio estático lo sepa sin que se lo
   digan. */
(function () {
  "use strict";

  // It is a <details>, so it already opens, closes and reaches the keyboard on
  // its own. This adds the two things a browser does not.
  var menu = document.querySelector("[data-usermenu]");
  if (menu) {
    document.addEventListener("click", function (e) {
      if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && menu.open) {
        menu.open = false;
        var button = menu.querySelector("summary");
        if (button) button.focus();
      }
    });
  }

  var grupo = document.querySelector("[data-account]");
  if (!grupo) return;
  var crumb = /(^|;\s*)pm_in=([^;]*)/.exec(document.cookie);
  if (!crumb) return;
  var admin = crumb[2] === "admin";

  // Signed in: the two buttons give way to the account's own face, and the
  // three rows that need a session appear inside the menu.
  grupo.querySelector("[data-account-in]").hidden = true;
  grupo.querySelector("[data-account-up]").hidden = true;
  if (!menu) return;

  var bars = menu.querySelector("[data-usermenu-bars]");
  var me = menu.querySelector("[data-usermenu-me]");
  var label = menu.querySelector("[data-usermenu-label]");
  if (bars) bars.hidden = true;
  // "Mi cuenta" names the button from here on, so the hidden word would only
  // be read out twice.
  if (label) label.hidden = true;
  if (me) me.hidden = false;
  Array.prototype.forEach.call(menu.querySelectorAll("[data-account-only]"),
                               function (row) { row.hidden = false; });
  // Las que dependen de quién es: administración para uno, panel y contactos
  // para el otro.
  var suyas = admin ? "[data-admin-only]" : "[data-client-only]";
  Array.prototype.forEach.call(menu.querySelectorAll(suyas),
                               function (row) { row.hidden = false; });
})();
