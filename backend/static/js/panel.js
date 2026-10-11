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

  // Written on the parent domain so sobreala.com and app.sobreala.com read
  // the same choice. Anywhere else (a local run) it stays on the host, which is
  // shared anyway: cookies ignore ports.
  function rememberTheme(theme) {
    var parent = /(^|\.)sobreala\.com$/.test(location.hostname)
      ? "; domain=.sobreala.com" : "";
    var secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = "sa_theme=" + theme + "; path=/; max-age=31536000; SameSite=Lax"
      + parent + secure;
  }

  // A choice made before the crumb existed lives only in this origin's
  // storage: copy it over once, so the other site learns it too.
  if (!/(?:^|;\s*)sa_theme=/.test(document.cookie)) {
    var saved = null;
    try { saved = localStorage.getItem("theme"); } catch (e) {}
    if (saved === "dark" || saved === "light") rememberTheme(saved);
  }

  // The server drew the light-mode row; the head script may have chosen dark.
  if (themeLabel && currentTheme() === "dark") themeLabel.textContent = MODE.light;

  themeBtn.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", next); } catch (e) {}
    rememberTheme(next);
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

/* Los formularios que no se pueden mandar dos veces (data-once): los que abren
   una sesión, crean una cuenta o piden un código. Un doble clic mientras el
   servidor contestaba abría dos sesiones, y la que se quedaba sin galleta
   seguía viva en Seguridad como otro dispositivo; en el código, la segunda
   vuelta decía que ya se había usado. Sin JavaScript se mandan como siempre. */
(function () {
  "use strict";

  var forms = document.querySelectorAll("form[data-once]");
  if (!forms.length) return;

  Array.prototype.forEach.call(forms, function (form) {
    form.addEventListener("submit", function (e) {
      if (e.defaultPrevented) return;
      if (form.hasAttribute("data-sent")) {
        e.preventDefault();
        return;
      }
      form.setAttribute("data-sent", "");
    });
  });

  // Volver con «atrás» saca la página de la memoria del navegador tal como
  // quedó, ya mandada: sin esto el formulario dejaría de responder.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    Array.prototype.forEach.call(forms, function (form) {
      form.removeAttribute("data-sent");
    });
  });
})();

/* El nombre del archivo elegido, al lado del botón. El control del navegador
   queda escondido, así que sin esto no habría forma de comprobar que se eligió
   el que se quería. Sin JavaScript el botón sigue abriendo el selector. */
(function () {
  var input = document.querySelector(".filepick__input");
  if (!input) return;
  var name = document.querySelector("[data-file-name]");
  if (!name) return;
  var empty = name.textContent;

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    name.textContent = file ? file.name : empty;
    name.classList.toggle("is-set", !!file);
  });
})();

/* Elegir qué columnas del archivo se guardan, al importar contactos.

   La primera línea del CSV se lee aquí, en el navegador, con FileReader: así
   el archivo no hay que subirlo dos veces ni guardarlo en el servidor
   mientras alguien decide. Lo que se manda son los desplegables; el servidor
   vuelve a leer esa misma cabecera y no se fía de nada de esto.

   Sin JavaScript el bloque se queda escondido y la importación sigue
   funcionando: el servidor casa los títulos con las columnas que ya existen. */
(function () {
  var input = document.querySelector(".filepick__input");
  var box = document.querySelector("[data-map-columns]");
  if (!input || !box) return;

  var rows = box.querySelector("[data-map-rows]");
  var room = box.querySelector("[data-map-room]");
  var choiceTpl = document.querySelector("[data-map-choice]");
  var typeTpl = document.querySelector("[data-map-type]");
  if (!rows || !choiceTpl || !typeTpl) return;

  var left = parseInt(room && room.getAttribute("data-room"), 10);
  if (isNaN(left)) left = 0;

  /* El separador, contando cuál aparece más. Excel en español escribe punto y
     coma; casi todo lo demás, coma. */
  function apart(line) {
    var best = ",", most = -1;
    [",", ";", "\t", "|"].forEach(function (one) {
      var many = line.split(one).length - 1;
      if (many > most) { most = many; best = one; }
    });
    return best;
  }

  /* Una línea de CSV en celdas, respetando las comillas. */
  function cells(line, sep) {
    var out = [], current = "", quoted = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line[i];
      if (ch === '"') {
        if (quoted && line[i + 1] === '"') { current += '"'; i++; }
        else quoted = !quoted;
      } else if (ch === sep && !quoted) { out.push(current); current = ""; }
      else current += ch;
    }
    out.push(current);
    return out.map(function (one) { return one.trim(); });
  }

  /* Sin acentos y en minúsculas, para comparar un título con los conocidos.
     Es lo mismo que hace fold() en el servidor. */
  function fold(text) {
    return String(text || "").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
  }

  var known = (box.getAttribute("data-known") || "").split(",").map(fold);

  function draw(header) {
    rows.innerHTML = "";
    header.forEach(function (title, index) {
      /* El correo y el nombre no se preguntan: el servidor ya los reconoce por
         su título, y ofrecerlos aquí invitaría a guardar la dirección dentro
         de una columna propia. */
      if (!title || known.indexOf(fold(title)) >= 0) return;
      var row = document.createElement("div");
      row.className = "mapcols__row";

      var name = document.createElement("span");
      name.className = "mapcols__name";
      name.textContent = title;
      row.appendChild(name);

      var choice = choiceTpl.content.firstElementChild.cloneNode(true);
      choice.name = "columna-" + index;
      choice.id = "columna-" + index;
      name.setAttribute("for", choice.id);
      row.appendChild(choice);

      var kind = typeTpl.content.firstElementChild.cloneNode(true);
      kind.name = "tipo-" + index;
      kind.hidden = true;
      row.appendChild(kind);

      /* El tipo solo se pregunta cuando la columna se va a crear: para una que
         ya existe, el tipo ya está decidido y preguntarlo otra vez sería
         ofrecer cambiarlo por la puerta de atrás. */
      choice.addEventListener("change", function () {
        kind.hidden = choice.value !== "nueva";
        count();
      });
      rows.appendChild(row);
    });
    box.hidden = header.length === 0;
    count();
  }

  /* Cuántas se están creando, contra las que caben. Es un aviso, no una
     puerta: la que cierra es la del servidor. */
  function count() {
    if (!room) return;
    var many = 0;
    rows.querySelectorAll("select[name^='columna-']").forEach(function (one) {
      if (one.value === "nueva") many++;
    });
    room.classList.toggle("is-full", many > left);
  }

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    box.hidden = true;
    rows.innerHTML = "";
    if (!file) return;

    var reader = new FileReader();
    reader.onload = function () {
      var text = String(reader.result || "");
      var line = text.split(/\r\n|\r|\n/)[0] || "";
      /* Una primera línea con una dirección dentro son datos, no títulos: ese
         archivo no tiene nada que mapear. */
      if (!line.trim() || line.indexOf("@") >= 0) return;
      draw(cells(line, apart(line)));
    };
    /* Solo el principio: la cabecera está ahí y el archivo puede pesar megas. */
    reader.readAsText(file.slice(0, 64 * 1024));
  });
})();

/* Escribir una columna dentro de la pieza, donde esté el cursor.

   Los botones llevan la marca escrita —*|CIUDAD|*—, así que sin JavaScript se
   puede leer y copiar a mano; lo que esto agrega es pegarla en el sitio donde
   se estaba escribiendo. */
(function () {
  var box = document.querySelector("[data-marks]");
  if (!box) return;
  var form = box.closest("form") || document;
  var last = null;

  form.addEventListener("focusin", function (e) {
    var one = e.target;
    if (one && (one.tagName === "TEXTAREA" ||
                (one.tagName === "INPUT" && one.type === "text"))) {
      last = one;
    }
  });

  box.addEventListener("click", function (e) {
    var button = e.target.closest("[data-mark]");
    if (!button) return;
    var mark = button.getAttribute("data-mark");
    /* Sin un campo tocado no se adivina: la marca se queda para copiar. */
    if (!last) return;
    var start = last.selectionStart, end = last.selectionEnd;
    if (start === null || start === undefined) {
      last.value += mark;
    } else {
      last.value = last.value.slice(0, start) + mark + last.value.slice(end);
      last.selectionStart = last.selectionEnd = start + mark.length;
    }
    last.focus();
    /* Para que quien escucha lo escrito (la vista previa en vivo) se entere. */
    last.dispatchEvent(new Event("input", { bubbles: true }));
  });
})();

/* La bandeja de cargar una plantilla. El botón es un enlace a su propia
   página; con JavaScript, en vez de irse, abre la bandeja con el mismo
   formulario. */
(function () {
  Array.prototype.forEach.call(document.querySelectorAll("[data-open-dialog]"), function (link) {
    var dialog = document.getElementById(link.getAttribute("data-open-dialog"));
    if (!dialog || typeof dialog.showModal !== "function") return;
    link.addEventListener("click", function (e) {
      e.preventDefault();
      dialog.showModal();
    });
    Array.prototype.forEach.call(dialog.querySelectorAll("[data-close-dialog]"), function (btn) {
      btn.addEventListener("click", function () { dialog.close(); });
    });
    /* Un clic fuera de la bandeja, en el fondo oscuro, también la cierra. */
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) dialog.close();
    });
  });
})();

/* La vista previa que se refresca sola al escribir. Pulsa por su cuenta el
   botón de ver cómo queda, que manda al marco de al lado: la respuesta trae
   su propia cabecera de correo, cosa que un marco llenado desde aquí no
   tendría. Espera a que se deje de escribir un momento. */
(function () {
  var form = document.querySelector("[data-live-preview]");
  if (!form || typeof form.requestSubmit !== "function") return;
  var button = form.querySelector("[data-preview-button]");
  if (!button) return;
  var timer = null;
  function refresh() { form.requestSubmit(button); }
  form.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(refresh, 700);
  });
  // El selector de contacto está al otro lado de la pantalla, fuera del
  // formulario aunque viaje con él: sus cambios no llegan por «input».
  var person = document.querySelector("[data-preview-contact]");
  if (person) person.addEventListener("change", refresh);
  refresh();
})();

/* Las imágenes de un HTML cargado: «Cambiar» sube una foto a la cuenta por la
   ruta de siempre (que la revisa, la achica y la cuenta contra el tope) y
   cambia su dirección en el código. El panel no va a buscar la de fuera: la
   sube quien la tiene. Se guarda con Guardar, como cualquier cambio. */
(function () {
  var box = document.querySelector("[data-pictures]");
  var code = document.getElementById("html");
  if (!box || !code || !window.fetch || !window.FormData) return;
  var file = box.querySelector("[data-picture-file]");
  var error = box.querySelector("[data-picture-error]");
  var form = code.form;
  var row = null;
  Array.prototype.forEach.call(box.querySelectorAll("[data-picture-change]"), function (b) {
    b.hidden = false;
  });
  box.addEventListener("click", function (e) {
    var b = e.target.closest("[data-picture-change]");
    if (!b) return;
    row = b.closest("[data-src]");
    file.value = "";
    file.click();
  });
  // Dentro del formulario: sin esto, elegir el archivo refrescaría la vista.
  file.addEventListener("input", function (e) { e.stopPropagation(); });
  file.addEventListener("change", function (e) {
    e.stopPropagation();
    var picked = file.files && file.files[0];
    if (!picked || !row) return;
    var body = new FormData();
    body.append("csrf_token", form.querySelector("[name=csrf_token]").value);
    body.append("archivo", picked);
    error.hidden = true;
    fetch(box.getAttribute("data-upload"), { method: "POST", body: body, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (answer) {
        if (!answer.url) throw new Error(answer.error || "");
        var old = row.getAttribute("data-src");
        code.value = code.value.split(old).join(answer.url);
        row.setAttribute("data-src", answer.url);
        row.className = "pictures__one is-ok";
        row.querySelector("[data-picture-shown]").textContent = answer.url;
        row.querySelector("[data-picture-state]").textContent = box.getAttribute("data-ok-text");
        var warn = box.querySelector("[data-pictures-warn]");
        if (warn && !box.querySelector(".pictures__one:not(.is-ok)")) warn.hidden = true;
        // Que la vista previa se entere, como si se hubiera escrito.
        code.dispatchEvent(new Event("input", { bubbles: true }));
      })
      .catch(function (err) {
        error.textContent = err.message || "";
        error.hidden = !err.message;
      });
  });
})();

/* Ver la vista previa como en una computadora o como en un teléfono. Es una
   clase en el marco: lo de dentro no se toca, sigue aislado. */
(function () {
  var frame = document.querySelector("[data-preview-frame]");
  if (!frame) return;
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-preview-view]");
    if (!b) return;
    var phone = b.getAttribute("data-preview-view") === "phone";
    frame.classList.toggle("is-phone", phone);
    Array.prototype.forEach.call(document.querySelectorAll("[data-preview-view]"), function (one) {
      var on = one === b;
      one.classList.toggle("is-on", on);
      one.setAttribute("aria-pressed", on ? "true" : "false");
    });
  });
})();

/* Los teléfonos de la empresa: hasta tres. Sin este guion se ven los tres
   campos; con él, solo los que tienen algo y uno vacío, y «Agregar otro número»
   enseña el siguiente. Un campo vacío no se guarda, así que esconderlo no
   pierde nada. */
(function () {
  Array.prototype.forEach.call(document.querySelectorAll("[data-more]"), function (box) {
    var rows = Array.prototype.slice.call(box.querySelectorAll("[data-more-row]"));
    var add = box.querySelector("[data-more-add]");
    if (!rows.length || !add) return;
    function filled(row) { return row.querySelector("input").value.trim() !== ""; }
    var shownEmpty = false;
    rows.forEach(function (row) {
      if (filled(row)) return;
      if (!shownEmpty) { shownEmpty = true; return; }
      row.hidden = true;
    });
    function refresh() {
      add.hidden = !rows.some(function (row) { return row.hidden; });
    }
    add.addEventListener("click", function () {
      var next = rows.filter(function (row) { return row.hidden; })[0];
      if (!next) return;
      next.hidden = false;
      next.querySelector("input").focus();
      refresh();
    });
    refresh();
  });
})();
