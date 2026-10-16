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

/* Escribir o Plantilla (octubre de 2026), en Redactar y en Masivo: se ve solo
   la parte de lo elegido. Sin JavaScript se ven las dos, y el servidor usa la
   elegida. */
(function () {
  Array.prototype.forEach.call(document.querySelectorAll("[data-mode]"), function (box) {
    var form = box.closest("form");
    if (!form) return;
    function paint() {
      var chosen = form.querySelector('input[name="modo"]:checked');
      var value = chosen ? chosen.value : "";
      Array.prototype.forEach.call(form.querySelectorAll("[data-mode-part]"), function (part) {
        part.hidden = part.getAttribute("data-mode-part") !== value;
      });
    }
    box.addEventListener("change", paint);
    paint();
  });
})();

/* Las ramas del árbol del Dashboard (octubre de 2026): en una pantalla ancha,
   pulsar una rama la despliega o la recoge sin recargar; la animación la hace
   el CSS. En el teléfono el enlace va a su primera fila. Sin JavaScript,
   también. Nació para el menú de Configuración, que ya no se despliega: de ahí
   el nombre del atributo. */
(function () {
  var heads = document.querySelectorAll("[data-settings-toggle]");
  if (!heads.length || !window.matchMedia) return;
  var wide = window.matchMedia("(min-width: 780px)");
  Array.prototype.forEach.call(heads, function (head) {
    head.addEventListener("click", function (e) {
      if (!wide.matches) return;
      e.preventDefault();
      var group = head.parentNode;
      var open = !group.classList.contains("is-open");
      group.classList.toggle("is-open", open);
      head.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });
})();

/* El árbol del Dashboard en el teléfono (octubre de 2026): se esconde detrás
   de «Secciones» para que lo primero que se vea sea la pantalla y no el menú.
   Sin JavaScript el árbol sale entero, que es peor de mirar pero funciona. Las
   ramas se despliegan con el mismo código que Configuración, de arriba. */
(function () {
  var nav = document.querySelector("[data-dash-nav]");
  if (!nav) return;
  var button = nav.querySelector("[data-dash-toggle]");
  if (!button) return;
  button.hidden = false;
  nav.classList.add("is-collapsible");
  button.addEventListener("click", function () {
    var shown = !nav.classList.contains("is-shown");
    nav.classList.toggle("is-shown", shown);
    button.setAttribute("aria-expanded", shown ? "true" : "false");
  });
})();

/* La búsqueda (octubre de 2026), en la barra de arriba del Dashboard y de
   Administración, al lado del ala. Mientras se escribe, pide las
   sugerencias al panel (`/search/suggest`) y las enseña debajo; las flechas
   las recorren, Enter abre la marcada (sin marcar, el formulario manda a la
   página de resultados, que es lo que pasa sin JavaScript) y Esc la cierra.
   «/» lleva al campo desde cualquier parte que no sea otro campo. Lo que
   llega se pinta con textContent: los nombres los escribió el cliente. */
(function () {
  var form = document.querySelector("form[data-search]");
  if (!form || !window.fetch) return;
  var input = form.querySelector(".search__input");
  var list = form.querySelector(".search__list");
  var url = form.getAttribute("data-suggest");
  var timer = null;
  var active = -1;
  var asked = 0;

  function options() { return list.querySelectorAll(".search__option"); }

  function close() {
    list.hidden = true;
    list.innerHTML = "";
    active = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function mark(index) {
    var all = options();
    Array.prototype.forEach.call(all, function (one, i) {
      one.classList.toggle("is-active", i === index);
      one.setAttribute("aria-selected", i === index ? "true" : "false");
    });
    active = index;
    if (index >= 0 && all[index]) {
      input.setAttribute("aria-activedescendant", all[index].id);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function draw(items) {
    list.innerHTML = "";
    if (!items.length) {
      var none = document.createElement("li");
      none.className = "search__empty";
      none.textContent = form.getAttribute("data-none") || "Nada coincide.";
      list.appendChild(none);
    }
    items.forEach(function (item, i) {
      var li = document.createElement("li");
      li.className = "search__option";
      li.id = "buscar-opcion-" + i;
      li.setAttribute("role", "option");
      var link = document.createElement("a");
      link.href = item.url;
      var label = document.createElement("span");
      label.textContent = item.label;
      link.appendChild(label);
      if (item.hint) {
        var hint = document.createElement("span");
        hint.className = "search__hint";
        hint.textContent = item.hint;
        link.appendChild(hint);
      }
      li.appendChild(link);
      list.appendChild(li);
    });
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    mark(-1);
  }

  function ask() {
    var q = input.value.trim();
    if (!q) { close(); return; }
    var mine = ++asked;
    fetch(url + "?q=" + encodeURIComponent(q), {
      credentials: "same-origin", headers: { "Accept": "application/json" }
    })
      .then(function (answer) { return answer.ok ? answer.json() : { items: [] }; })
      .then(function (data) {
        // Solo la última pregunta: una respuesta lenta no pisa a una nueva.
        if (mine === asked && input.value.trim()) draw(data.items || []);
      })
      .catch(function () {});
  }

  input.addEventListener("input", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(ask, 140);
  });

  input.addEventListener("keydown", function (e) {
    var all = options();
    if (e.key === "ArrowDown" && all.length) {
      e.preventDefault();
      mark(active + 1 < all.length ? active + 1 : 0);
    } else if (e.key === "ArrowUp" && all.length) {
      e.preventDefault();
      mark(active > 0 ? active - 1 : all.length - 1);
    } else if (e.key === "Enter" && active >= 0 && all[active]) {
      e.preventDefault();
      window.location.href = all[active].querySelector("a").href;
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });

  document.addEventListener("click", function (e) {
    if (!form.contains(e.target)) close();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (document.activeElement && document.activeElement.tagName) || "";
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag) || document.activeElement.isContentEditable) return;
    e.preventDefault();
    input.focus();
  });
})();

/* Los botones que trabajan (octubre de 2026). Al mandar un formulario, el botón
   pulsado se queda con su ancho y cambia su texto por el ícono que gira (el
   texto sigue ahí para quien escucha la pantalla); no se puede pulsar dos
   veces. Al volver la página con su aviso verde, el aviso dibuja el círculo y
   la palomita. Una descarga no cambia de página: el botón manda una ficha
   (`dl`), el servidor la devuelve en la galleta `sa_dl` cuando el archivo sale,
   y el botón dibuja la palomita un momento y vuelve a ser el de antes. Con
   «reducir movimiento», los íconos salen quietos. */
(function () {
  var spin = document.getElementById("icono-cargando");
  var check = document.getElementById("icono-listo");
  if (!spin || !check) return;
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function icon(template, end) {
    var svg = template.content.firstElementChild.cloneNode(true);
    // Cada copia empieza su animación al entrar en la página; quieta, se
    // queda en su último cuadro.
    window.requestAnimationFrame(function () {
      if (!svg.setCurrentTime) return;
      if (still) { svg.pauseAnimations(); svg.setCurrentTime(end); }
      else svg.setCurrentTime(0);
    });
    return svg;
  }

  function busy(btn) {
    if (btn.classList.contains("is-busy")) return;
    btn.setAttribute("data-label", btn.innerHTML);
    btn.style.width = btn.getBoundingClientRect().width + "px";
    var label = document.createElement("span");
    label.className = "visually-hidden";
    label.textContent = btn.textContent.trim();
    btn.innerHTML = "";
    btn.appendChild(icon(spin, 0.4));
    btn.appendChild(label);
    btn.classList.add("is-busy");
    btn.setAttribute("aria-busy", "true");
  }

  function restore(btn) {
    if (!btn.hasAttribute("data-label")) return;
    btn.innerHTML = btn.getAttribute("data-label");
    btn.removeAttribute("data-label");
    btn.style.width = "";
    btn.classList.remove("is-busy", "is-done");
    btn.removeAttribute("aria-busy");
  }

  function done(btn) {
    var label = btn.querySelector(".visually-hidden");
    btn.innerHTML = "";
    btn.appendChild(icon(check, 1));
    if (label) btn.appendChild(label);
    btn.classList.remove("is-busy");
    btn.classList.add("is-done");
    btn.removeAttribute("aria-busy");
    window.setTimeout(function () { restore(btn); }, 1600);
  }

  function token() {
    var out = "";
    var chars = "abcdefghijklmnopqrstuvwxyz0123456789";
    for (var i = 0; i < 16; i++) out += chars.charAt(Math.floor(Math.random() * chars.length));
    return out;
  }

  function arrived(value) {
    return document.cookie.split(/;\s*/).indexOf("sa_dl=" + value) !== -1;
  }

  function watch(btn, value) {
    var started = Date.now();
    var timer = window.setInterval(function () {
      if (arrived(value)) {
        window.clearInterval(timer);
        document.cookie = "sa_dl=; path=/; max-age=0";
        done(btn);
      } else if (Date.now() - started > 20000) {
        window.clearInterval(timer);
        restore(btn);
      }
    }, 250);
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form || (form.method || "").toLowerCase() !== "post") return;
    if (form.hasAttribute("target") || form.hasAttribute("data-no-busy")) return;
    if (form.hasAttribute("data-busy-sent")) { e.preventDefault(); return; }
    var btn = e.submitter;
    if (!btn || !btn.classList || !btn.classList.contains("btn")) return;
    if (form.hasAttribute("data-download")) {
      var value = token();
      var field = form.querySelector('input[name="dl"]');
      if (!field) {
        field = document.createElement("input");
        field.type = "hidden";
        field.name = "dl";
        form.appendChild(field);
      }
      field.value = value;
      busy(btn);
      watch(btn, value);
      return;
    }
    form.setAttribute("data-busy-sent", "");
    // Se marca después de que el navegador lea el botón: su nombre y su valor
    // viajan con el formulario («Usar gmail.com», «Quitar el límite»).
    window.setTimeout(function () { busy(btn); }, 0);
  });

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a[data-download]") : null;
    if (!link || link.classList.contains("is-busy")) return;
    var value = token();
    var href = link.getAttribute("href");
    link.setAttribute("href", href.replace(/([?&])dl=[^&]*&?/, "$1") + (href.indexOf("?") === -1 ? "?" : "&") + "dl=" + value);
    busy(link);
    watch(link, value);
  });

  // Volver con «atrás» saca la página de la memoria tal como quedó, girando.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    Array.prototype.forEach.call(document.querySelectorAll(".is-busy"), restore);
    Array.prototype.forEach.call(document.querySelectorAll("form[data-busy-sent]"), function (form) {
      form.removeAttribute("data-busy-sent");
    });
  });

  // Los avisos bajan desde arriba, como una notificación del teléfono (octubre
  // de 2026): el verde de lo que se guardó, con su palomita, y el gris de «No
  // se realizaron cambios». Se van solos a los cuatro segundos (quietos
  // mientras el ratón está encima) y tienen su «×». Solo los de una frase: uno
  // con un enlace o un botón se queda en su sitio, porque se iría con lo que
  // hay que pulsar. El texto se copia con textContent.
  var shelf = document.getElementById("toasts");
  var same = document.getElementById("icono-igual");
  if (shelf) {
    Array.prototype.forEach.call(document.querySelectorAll("p.notice--ok, p.notice--same"), function (note) {
      if (note.querySelector("a, button, form, input")) return;
      var gray = note.classList.contains("notice--same");
      var toast = document.createElement("div");
      toast.className = "toast" + (gray ? " toast--same" : "");
      var mark = document.createElement("span");
      mark.className = "toast__icon";
      if (gray && same) mark.appendChild(same.content.firstElementChild.cloneNode(true));
      else mark.appendChild(icon(check, 1));
      var text = document.createElement("span");
      text.className = "toast__text";
      text.textContent = note.textContent.trim();
      var close = document.createElement("button");
      close.type = "button";
      close.className = "toast__close";
      close.setAttribute("aria-label", shelf.getAttribute("data-close") || "Cerrar");
      close.textContent = "×";
      toast.appendChild(mark);
      toast.appendChild(text);
      toast.appendChild(close);
      note.parentNode.removeChild(note);
      shelf.appendChild(toast);

      var timer = null;
      function leave() {
        window.clearTimeout(timer);
        toast.classList.remove("is-in");
        window.setTimeout(function () {
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, still ? 0 : 320);
      }
      function wait(ms) {
        window.clearTimeout(timer);
        timer = window.setTimeout(leave, ms);
      }
      close.addEventListener("click", leave);
      toast.addEventListener("mouseenter", function () { window.clearTimeout(timer); });
      toast.addEventListener("mouseleave", function () { wait(2000); });
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () { toast.classList.add("is-in"); });
      });
      wait(4000);
    });
  }

  // Los avisos verdes que se quedan en su sitio dibujan su palomita al aparecer.
  Array.prototype.forEach.call(document.querySelectorAll(".notice--ok"), function (note) {
    if (note.querySelector(".notice__check")) return;
    var holder = document.createElement("span");
    holder.className = "notice__check";
    holder.appendChild(icon(check, 1));
    var first = note.firstElementChild && note.firstElementChild.tagName === "P"
      ? note.firstElementChild : note;
    first.insertBefore(holder, first.firstChild);
  });
})();

/* Guardar no mueve la pantalla (octubre de 2026). Antes de mandar un
   formulario, o de pulsar un enlace con data-keep-scroll («Editar» y
   «Cancelar»), se anota a qué altura estaba la página; el guion de la cabecera
   de base.html vuelve ahí si lo que llega es esta misma página, o la del
   formulario con su error. Antes el panel volvía con un ancla (#address,
   #logo…) y el navegador bajaba hasta ella. Los que bajan un archivo o abren
   otra pestaña no cambian de página y no se anotan. La dirección se lee con
   getAttribute: un campo llamado «action» tapa form.action. */
(function () {
  function keep(to) {
    try {
      window.sessionStorage.setItem("sa_scroll", JSON.stringify({
        paths: [location.pathname, new URL(to || "", location.href).pathname],
        y: window.scrollY || window.pageYOffset || 0, at: Date.now()}));
    } catch (err) {}
  }
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form || !form.getAttribute) return;
    if ((form.getAttribute("method") || "").toLowerCase() !== "post") return;
    if (form.hasAttribute("target") || form.hasAttribute("data-download")) return;
    keep(form.getAttribute("action"));
  });
  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a[data-keep-scroll]") : null;
    if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
    keep(link.getAttribute("href"));
  });
})();

/* Las funciones que rotan al lado de entrar y registrarse (octubre de 2026,
   _auth.html). Cada 6 s pasa a la siguiente, y los puntitos eligen una y
   vuelven a contar. Se para con el ratón encima, con el foco dentro, con la
   pestaña escondida y en el teléfono, donde no se ven; con «reducir
   movimiento» no avanza sola. Sin JavaScript se queda la primera. */
(function () {
  var tour = document.querySelector("[data-auth-tour]");
  var row = tour && tour.querySelector("[data-dots]");
  var slides = tour ? tour.querySelectorAll("[data-slide]") : [];
  if (!row || slides.length < 2) return;
  var dots = row.querySelectorAll("[data-dot]");
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var current = 0;
  var held = false;
  var timer = null;
  row.hidden = false;

  function show(n) {
    current = (n + slides.length) % slides.length;
    Array.prototype.forEach.call(slides, function (slide, i) {
      slide.classList.toggle("is-on", i === current);
      if (i === current) slide.removeAttribute("aria-hidden");
      else slide.setAttribute("aria-hidden", "true");
    });
    Array.prototype.forEach.call(dots, function (dot, i) {
      dot.setAttribute("aria-pressed", i === current ? "true" : "false");
    });
  }

  function plan() {
    if (still) return;
    window.clearTimeout(timer);
    timer = window.setTimeout(function () {
      if (!held && !document.hidden && tour.offsetParent !== null) show(current + 1);
      plan();
    }, 6000);
  }

  Array.prototype.forEach.call(dots, function (dot) {
    dot.addEventListener("click", function () {
      show(Number(dot.getAttribute("data-dot")));
      plan();
    });
  });
  tour.addEventListener("mouseenter", function () { held = true; });
  tour.addEventListener("mouseleave", function () { held = false; });
  tour.addEventListener("focusin", function () { held = true; });
  tour.addEventListener("focusout", function () { held = false; });
  plan();
})();
