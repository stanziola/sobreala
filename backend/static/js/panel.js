/* The bar menu and the theme switch inside it. No dependencies.
   The same behaviour as the landing site's nav.js, without the mobile menu. */
(function () {
  "use strict";

  // --- the menu ------------------------------------------------------------
  // It is a <details>, so it already opens, closes and reaches the keyboard on
  // its own. This adds the two things a browser does not: Escape, and clicking
  // somewhere else.
  var menu = document.querySelector("[data-menu]");
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

  // --- the theme -----------------------------------------------------------
  // The head script already set data-theme before the first paint. Here we only
  // handle switching it, remembering the choice, and the reveal animation.

  var themeBtn = document.getElementById("theme-toggle");
  var themeStatus = document.getElementById("theme-status");
  var themeMeta = document.getElementById("theme-color");
  var THEME_COLOR = { light: "#3166A7", dark: "#245285" };
  if (!themeBtn) return;

  // The name of each mode, from the server, so the Spanish stays in i18n.py.
  // The row offers the other one; the status announces the one now on.
  var themeLabel = themeBtn.querySelector("[data-theme-label]");
  var MODE = { light: themeBtn.dataset.modeLight, dark: themeBtn.dataset.modeDark };

  function currentTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function paintTheme(theme) {
    document.documentElement.dataset.theme = theme;
    if (themeMeta) themeMeta.setAttribute("content", THEME_COLOR[theme]);
    // The row says what pressing it will do, not what is on.
    if (themeLabel) themeLabel.textContent = theme === "dark" ? MODE.light : MODE.dark;
  }

  // The server drew the light-mode row; the head script may have chosen dark.
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
})();

/* Passwords: seeing what you type, and the rules lighting up as they are met.
   In its own function because the one above gives up when there is no theme
   button, and this has to work all the same. */
(function () {
  "use strict";

  // --- fields the browser may not fill by itself ---------------------------
  // "Prove it is you" fields — the current password before changing it, and
  // before turning two-step on or off. An inline script in the page made them
  // read-only, so the password manager skipped them; here they open at the
  // first touch, and from that moment the browser offers the saved one like
  // anywhere else. What it can no longer do is answer for somebody who just
  // sat down at an open session.
  Array.prototype.forEach.call(document.querySelectorAll("[data-fill-on-click]"),
                               function (input) {
    function open() {
      input.readOnly = false;
      input.removeEventListener("pointerdown", open);
      input.removeEventListener("focus", open);
    }
    input.addEventListener("pointerdown", open);
    input.addEventListener("focus", open);
  });

  // --- show the password ---------------------------------------------------
  Array.prototype.forEach.call(document.querySelectorAll("[data-reveal]"), function (btn) {
    var input = document.getElementById(btn.dataset.reveal);
    if (!input) return;

    // Born hidden in the HTML: without this script the button would do nothing.
    btn.hidden = false;

    btn.addEventListener("click", function () {
      var oculta = input.type === "password";
      input.type = oculta ? "text" : "password";
      btn.setAttribute("aria-pressed", String(oculta));
      btn.setAttribute("aria-label", oculta ? btn.dataset.hide : btn.dataset.show);
      // Focus goes back to the field, with the caret at the end.
      var fin = input.value.length;
      input.focus({ preventScroll: true });
      try { input.setSelectionRange(fin, fin); } catch (e) {}
    });
  });

  // --- the four rules ------------------------------------------------------
  // The same checks as password_problem() in services/security.py, which is the
  // one that decides; this only shows them while you type. Unicode classes and
  // not [A-Z] or [0-9], because over there isupper() and isdigit() understand
  // any alphabet.
  var lista = document.querySelector("[data-rules]");
  var campo = lista && document.getElementById("password");
  if (!lista || !campo) return;

  var minimo = parseInt(lista.dataset.min, 10) || 10;
  var reglas = {
    length: function (v) { return v.length >= minimo; },
    upper: function (v) { return /\p{Lu}/u.test(v); },
    digit: function (v) { return /\p{Nd}/u.test(v); },
    symbol: function (v) { return /[^\p{L}\p{N}\s]/u.test(v); }
  };
  var puntos = Array.prototype.slice.call(lista.querySelectorAll("[data-rule]"));
  var cumplido = lista.dataset.metLabel || "cumplido";

  function repasar() {
    var valor = campo.value;
    puntos.forEach(function (punto) {
      var prueba = reglas[punto.dataset.rule];
      var ok = prueba ? prueba(valor) : false;
      punto.classList.toggle("is-met", ok);
      var estado = punto.querySelector("[data-state]");
      if (estado) estado.textContent = ok ? cumplido : "";
    });
  }

  campo.addEventListener("input", repasar);
  // The browser may fill the field on its own: the list must not lie on load.
  repasar();
})();

/* The six code boxes and the countdown above them. Third block of its own, so
   a page without any of this does not pay for it. */
(function () {
  "use strict";

  // --- the countdown -------------------------------------------------------
  // The server drew the starting state; this only makes the clock run. What it
  // shows decides nothing: the code's real expiry lives in the database.
  var clock = document.querySelector("[data-countdown]");
  var live = clock && clock.querySelector("[data-countdown-live]");
  var done = clock && clock.querySelector("[data-countdown-done]");
  var form = document.querySelector("[data-code-form]");
  var left = clock ? parseInt(clock.dataset.countdown, 10) : 0;

  function say(seconds) {
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function expire() {
    if (live) live.hidden = true;
    if (done) done.hidden = false;
    if (clock) clock.classList.add("is-expired");
    if (!form) return;
    // Nobody should spend a try on something the server will refuse anyway.
    Array.prototype.forEach.call(form.querySelectorAll("input.code__box, button"),
                                 function (el) { el.disabled = true; });
  }

  if (clock && left > 0) {
    live.textContent = clock.dataset.label.replace("{time}", say(left));
    var tick = setInterval(function () {
      left -= 1;
      if (left <= 0) {
        clearInterval(tick);
        expire();
        return;
      }
      live.textContent = clock.dataset.label.replace("{time}", say(left));
    }, 1000);
  }

  // --- the boxes -----------------------------------------------------------
  var group = document.querySelector("[data-code]");
  if (!group) return;
  var boxes = Array.prototype.slice.call(group.querySelectorAll(".code__box"));

  function digitsOf(text) {
    return (text || "").replace(/\D/g, "");
  }

  function fillFrom(index, digits) {
    for (var i = 0; i < digits.length && index + i < boxes.length; i++) {
      boxes[index + i].value = digits.charAt(i);
    }
    var last = Math.min(index + digits.length, boxes.length - 1);
    boxes[last].focus();
    boxes[last].select();
    return index + digits.length >= boxes.length;
  }

  function complete() {
    return boxes.every(function (b) { return b.value !== ""; });
  }

  boxes.forEach(function (box, index) {
    box.addEventListener("input", function () {
      var digits = digitsOf(box.value);
      if (!digits) {
        box.value = "";
        return;
      }
      // Typing over a full box, or a phone dropping the whole code in at once.
      box.value = digits.charAt(0);
      if (digits.length > 1) fillFrom(index, digits);
      else if (index < boxes.length - 1) boxes[index + 1].focus();
      if (complete() && form) form.requestSubmit ? form.requestSubmit() : form.submit();
    });

    box.addEventListener("keydown", function (e) {
      if (e.key === "Backspace" && !box.value && index > 0) {
        // Backspace on an empty box steps back, which is what the hand expects.
        e.preventDefault();
        boxes[index - 1].value = "";
        boxes[index - 1].focus();
      } else if (e.key === "ArrowLeft" && index > 0) {
        e.preventDefault();
        boxes[index - 1].focus();
      } else if (e.key === "ArrowRight" && index < boxes.length - 1) {
        e.preventDefault();
        boxes[index + 1].focus();
      }
    });

    box.addEventListener("paste", function (e) {
      var pasted = digitsOf((e.clipboardData || window.clipboardData).getData("text"));
      if (!pasted) return;
      e.preventDefault();
      var filled = fillFrom(index, pasted);
      if (filled && complete() && form) {
        form.requestSubmit ? form.requestSubmit() : form.submit();
      }
    });

    box.addEventListener("focus", function () { box.select(); });
  });
})();
