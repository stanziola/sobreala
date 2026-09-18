/* El lienzo de «Crear plantilla». Sin librerías: la cabecera del panel solo deja
   cargar guiones propios.

   El lienzo es un objeto en memoria ({h, bg, items: [...]}): una sola hoja de
   600 px que crece hacia abajo, y que se dibuja entera cada vez que cambia.
   Guardar lo manda en un campo escondido y el servidor lo vuelve a revisar todo
   (services/canvas.py): nada de lo que se comprueba aquí es una garantía, solo
   una ayuda para no perder el trabajo.

   Las fotos y los rectángulos van siempre atrás, en el orden de la lista, y los
   textos y botones delante: así es como llega el correo. */
(function () {
  "use strict";

  var root = document.querySelector("[data-canvas]");
  if (!root) return;

  var S = JSON.parse(root.getAttribute("data-strings") || "{}");
  var L = JSON.parse(root.getAttribute("data-limits") || "{}");
  var FONTS = JSON.parse(document.getElementById("canvas-fonts").textContent || "{}");
  var doc = JSON.parse(document.getElementById("canvas-doc").textContent || "{}");
  if (!doc.items) doc = { v: 2, h: 600, bg: "#FFFFFF", items: [] };

  var W = L.width || 600;
  var SNAP = 6;
  var FRONT = { text: true, button: true };
  var BACK = { image: true, shape: true };
  // Cuánto aire se deja debajo de lo último al agregar algo.
  var GAP = 20;

  var stage = root.querySelector("[data-stage]");
  var props = root.querySelector("[data-props]");
  var warn = root.querySelector("[data-canvas-warn]");
  var fileInput = root.querySelector("[data-canvas-file]");
  var errorBox = document.querySelector("[data-canvas-error]");
  var saveForm = document.querySelector("[data-canvas-save]");
  var previewForm = document.querySelector("[data-canvas-preview]");

  var sel = null;          // el índice del elemento elegido, o null
  var editing = null;      // el elemento de texto que se está escribiendo
  var lastField = null;    // el último campo de la barra que tuvo el cursor
  var dirty = false;
  var past = [], future = [];
  var saved = JSON.stringify(doc);

  /* ------------------------------------------------------------ utilidades */

  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function item() { return sel === null ? null : doc.items[sel] || null; }
  function linePx(one) { return Math.round(one.size * (one.line || 1.4)); }

  function say(text) {
    if (!errorBox) return;
    errorBox.textContent = text || "";
    errorBox.hidden = !text;
  }

  function touch(a, b) {
    return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  }

  /* Lo que no se puede guardar, para pintarlo en rojo: dos textos o botones
     encimados, y una foto con enlace que tiene algo encima (el enlace no
     sobrevive a fundirse con otra cosa). */
  function badOnes() {
    var bad = {};
    doc.items.forEach(function (a, i) {
      doc.items.forEach(function (b, j) {
        if (j <= i || !touch(a, b)) return;
        if (FRONT[a.t] && FRONT[b.t]) { bad[i] = "overlap"; bad[j] = "overlap"; }
        if (a.t === "image" && a.href) bad[i] = bad[i] || "link";
        if (b.t === "image" && b.href) bad[j] = bad[j] || "link";
      });
    });
    return bad;
  }

  function lowest() {
    var bottom = 0;
    doc.items.forEach(function (one) { bottom = Math.max(bottom, one.y + one.h); });
    return bottom;
  }

  /* La hoja crece sola cuando algo pasa del borde de abajo. */
  function grow() {
    var need = lowest();
    if (need > doc.h) doc.h = Math.min(need, L.maxHeight);
  }

  /* ------------------------------------------------------------- historia */

  function commit() {
    var now = JSON.stringify(doc);
    if (past.length && past[past.length - 1] === now) return;
    past.push(now);
    if (past.length > 80) past.shift();
    future = [];
    dirty = now !== saved;
    schedulePreview();
  }

  var commitTimer = null;
  function commitSoon() {
    clearTimeout(commitTimer);
    commitTimer = setTimeout(commit, 350);
  }

  function undo() {
    if (past.length < 2) return;
    future.push(past.pop());
    doc = JSON.parse(past[past.length - 1]);
    sel = null; editing = null;
    render(); schedulePreview();
  }

  function redo() {
    if (!future.length) return;
    var next = future.pop();
    past.push(next);
    doc = JSON.parse(next);
    sel = null; editing = null;
    render(); schedulePreview();
  }

  /* ------------------------------------------------------------- dibujar */

  function paintItem(el, one) {
    el.style.left = one.x + "px";
    el.style.top = one.y + "px";
    el.style.width = one.w + "px";
    el.style.height = one.h + "px";
    if (one.t === "image") {
      el.style.backgroundImage = "url('/img/" + encodeURIComponent(one.name) + "')";
      el.style.backgroundSize = one.fit === "contain" ? "contain" : "cover";
      return;
    }
    if (one.t === "shape") {
      el.style.backgroundColor = one.bg;
      el.style.borderRadius = one.radius + "px";
      return;
    }
    el.style.fontFamily = FONTS[one.font] || FONTS.Arial || "Arial, sans-serif";
    el.style.fontSize = one.size + "px";
    el.style.color = one.color;
    el.style.fontWeight = one.bold ? "bold" : "normal";
    el.style.fontStyle = one.italic ? "italic" : "normal";
    if (one.t === "text") {
      el.style.lineHeight = linePx(one) + "px";
      el.style.textAlign = one.align;
    } else {
      el.style.lineHeight = one.h + "px";
      el.style.backgroundColor = one.bg;
      el.style.borderRadius = one.radius + "px";
    }
  }

  // Las fotos y los rectángulos se tiran también de los lados: en una foto,
  // las esquinas guardan su proporción y los lados la recortan.
  var CORNERS = ["nw", "ne", "sw", "se"];
  var SIDES = ["n", "s", "e", "w"];

  function render() {
    // Vaciar el lienzo acorta la página un instante y el navegador salta de
    // posición: el segundo clic de un doble clic caería en otra cosa. Se
    // sostiene la altura y se vuelve a donde estaba.
    var scrollY = window.scrollY;
    stage.style.minHeight = stage.offsetHeight + "px";
    stage.textContent = "";

    var sheet = document.createElement("div");
    sheet.className = "cv-sheet";
    sheet.style.width = W + "px";
    sheet.style.height = doc.h + "px";
    sheet.style.backgroundColor = doc.bg;

    var bad = badOnes(), notes = {};
    doc.items.forEach(function (one, i) {
      var el = document.createElement("div");
      el.className = "cv-item cv-item--" + one.t;
      el.setAttribute("data-item", i);
      if (bad[i]) { el.className += " is-bad"; notes[bad[i]] = true; }
      if (sel === i) el.className += " is-sel";
      if (FRONT[one.t]) el.textContent = one.text;
      paintItem(el, one);
      if (sel === i) {
        var handles = BACK[one.t] ? CORNERS.concat(SIDES) : CORNERS;
        handles.forEach(function (where) {
          var h = document.createElement("span");
          h.className = "cv-handle cv-handle--" + where;
          h.setAttribute("data-handle", where);
          el.appendChild(h);
        });
      }
      sheet.appendChild(el);
    });
    stage.appendChild(sheet);

    var grip = document.createElement("div");
    grip.className = "cv-grip";
    grip.title = S.resizeSheet;
    grip.setAttribute("data-grip", "");
    stage.appendChild(grip);

    var said = [];
    if (notes.overlap) said.push(S.overlap);
    if (notes.link) said.push(S.linkOverlap);
    warn.textContent = said.join(" ");
    warn.hidden = !said.length;
    showProps();
    stage.style.minHeight = "";
    if (window.scrollY !== scrollY) window.scrollTo(window.scrollX, scrollY);
  }

  function showProps() {
    var one = item();
    var kind = one ? one.t : "none";
    Array.prototype.forEach.call(props.querySelectorAll("[data-props-for]"), function (row) {
      row.hidden = row.getAttribute("data-props-for").split(" ").indexOf(kind) < 0;
    });
    var page = props.querySelector("[data-page-bg]");
    if (page && page !== document.activeElement) page.value = doc.bg;
    if (!one) return;
    Array.prototype.forEach.call(props.querySelectorAll("[data-only]"), function (el) {
      el.hidden = el.getAttribute("data-only") !== kind;
    });
    var row = props.querySelector('[data-props-for~="' + kind + '"]');
    Array.prototype.forEach.call(row.querySelectorAll("[data-prop]"), function (input) {
      var name = input.getAttribute("data-prop");
      if (!(name in one)) return;
      if (input === document.activeElement) return;
      if (input.type === "checkbox") input.checked = !!one[name];
      else input.value = String(one[name]);
    });
  }

  /* Un texto crece para que quepa lo escrito: así el correo no lo corta. Y si
     pasa del borde de abajo, crece la hoja. */
  function fitText(i) {
    var one = doc.items[i];
    if (!one || one.t !== "text") return;
    var probe = document.createElement("div");
    probe.className = "cv-item cv-item--text cv-probe";
    probe.textContent = one.text || " ";
    paintItem(probe, one);
    probe.style.height = "auto";
    stage.appendChild(probe);
    var need = Math.ceil(probe.scrollHeight);
    stage.removeChild(probe);
    if (need > one.h) one.h = Math.min(need, L.maxHeight - one.y);
    grow();
  }

  /* ------------------------------------------------------------ agregar */

  /* Debajo de lo último, con aire. La hoja crece si hace falta. */
  function freeY(h) {
    var bottom = lowest();
    var y = bottom ? bottom + GAP : 40;
    return Math.max(0, Math.min(y, L.maxHeight - h));
  }

  function place(one) {
    if (doc.items.length >= L.maxItems) { say(S.maxItems); return; }
    one.y = freeY(one.h);
    doc.items.push(one);
    sel = doc.items.length - 1;
    grow();
    render(); commit();
    var el = stage.querySelector('[data-item="' + sel + '"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }

  function add(kind) {
    say("");
    if (doc.items.length >= L.maxItems) { say(S.maxItems); return; }
    if (kind === "image") { pickImage(null); return; }
    if (kind === "text") {
      place({ t: "text", x: 40, w: W - 80, h: 34, text: S.newText, font: "Arial",
              size: 22, color: "#18181B", bold: false, italic: false, align: "left", line: 1.4 });
    } else if (kind === "button") {
      place({ t: "button", x: (W - 200) / 2, w: 200, h: 48, text: S.newButton,
              href: "https://", font: "Arial", size: 16, color: "#FFFFFF", bg: "#31A9E8",
              bold: true, italic: false, align: "center", radius: 8 });
    } else if (kind === "shape") {
      place({ t: "shape", x: 0, w: W, h: 160, bg: "#E0F2FE", radius: 0 });
    }
  }

  /* Subir una foto. Con `replace`, cambia la del elemento elegido. */
  var replacing = null;
  function pickImage(replace) {
    replacing = replace;
    fileInput.value = "";
    fileInput.click();
  }

  fileInput.addEventListener("change", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) return;
    say(S.uploading);
    var body = new FormData();
    body.append("csrf_token", saveForm.querySelector("[name=csrf_token]").value);
    body.append("archivo", file);
    fetch(root.getAttribute("data-upload"), { method: "POST", body: body, credentials: "same-origin" })
      .then(function (r) { return r.json().catch(function () { return { error: S.uploadFailed }; }); })
      .then(function (answer) {
        if (answer.error || !answer.name) { say(answer.error || S.uploadFailed); return; }
        say("");
        var r = answer.width / Math.max(answer.height, 1);
        if (replacing !== null) {
          var one = doc.items[replacing];
          one.name = answer.name;
          one.r = Math.round(r * 10000) / 10000;
          // La caja toma la proporción de la foto nueva, con el mismo ancho.
          one.h = Math.max(16, Math.round(one.w / r));
          delete one.fit;
          grow();
          render(); commit();
          return;
        }
        // Entra a la mitad del ancho, con su proporción: se puede mover y
        // cabe otra al lado. «Ancho completo» la estira.
        var w = W / 2;
        var h = Math.max(16, Math.min(Math.round(w / r), L.maxHeight));
        place({ t: "image", x: Math.round((W - w) / 2), w: w, h: h, name: answer.name,
                r: Math.round(r * 10000) / 10000, href: "", alt: "" });
      })
      .catch(function () { say(S.uploadFailed); });
  });

  /* --------------------------------------------------- mover y cambiar tamaño */

  var drag = null;

  function guides(box, lines) {
    Array.prototype.forEach.call(box.querySelectorAll(".cv-guide"), function (g) { g.remove(); });
    lines.forEach(function (line) {
      var g = document.createElement("div");
      g.className = "cv-guide cv-guide--" + line.axis;
      if (line.axis === "x") g.style.left = line.at + "px"; else g.style.top = line.at + "px";
      box.appendChild(g);
    });
  }

  /* Las líneas a las que se pega: los bordes y el centro de la hoja a lo
     ancho, y los bordes y el centro de las demás cajas. */
  function snap(moving, x, y, w, h) {
    var xs = [0, W / 2, W], ys = [0];
    doc.items.forEach(function (one, i) {
      if (i === moving) return;
      xs.push(one.x, one.x + one.w / 2, one.x + one.w);
      ys.push(one.y, one.y + one.h / 2, one.y + one.h);
    });
    var lines = [];
    function best(pos, size, targets, axis) {
      var edges = [pos, pos + size / 2, pos + size], found = null;
      edges.forEach(function (edge) {
        targets.forEach(function (target) {
          var d = target - edge;
          if (Math.abs(d) <= SNAP && (!found || Math.abs(d) < Math.abs(found.d))) {
            found = { d: d, at: target };
          }
        });
      });
      if (!found) return pos;
      lines.push({ axis: axis, at: found.at });
      return pos + found.d;
    }
    return { x: best(x, w, xs, "x"), y: best(y, h, ys, "y"), lines: lines };
  }

  stage.addEventListener("pointerdown", function (e) {
    if (e.target.closest("[data-grip]")) {
      drag = { mode: "grip", y0: e.clientY, h0: doc.h,
               min: Math.max(L.minHeight, lowest()) };
      e.preventDefault();
      return;
    }
    var sheet = e.target.closest(".cv-sheet");
    if (!sheet) return;
    var el = e.target.closest(".cv-item");
    if (!el) {
      if (editing) editing.blur();
      sel = null;
      render();
      return;
    }
    if (el.isContentEditable) return;
    var i = +el.getAttribute("data-item");
    var handle = e.target.closest("[data-handle]");
    if (sel !== i) { sel = i; render(); }
    // Sin captura del puntero: con ella el doble clic le llegaría a la hoja
    // entera y no al texto. El movimiento se escucha en la ventana.
    // Mover se llama «drag» y no «move»: el tamaño se decide mirando si el
    // modo trae n, s, e u o, y «move» trae una e.
    drag = { mode: handle ? handle.getAttribute("data-handle") : "drag", i: i,
             x0: e.clientX, y0: e.clientY, start: clone(item()), moved: false };
    e.preventDefault();
  });

  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var sheet = stage.querySelector(".cv-sheet");
    if (drag.mode === "grip") {
      doc.h = clamp(Math.round(drag.h0 + e.clientY - drag.y0), drag.min, L.maxHeight);
      if (sheet) sheet.style.height = doc.h + "px";
      drag.moved = true;
      return;
    }
    var one = doc.items[drag.i], a = drag.start;
    var dx = Math.round(e.clientX - drag.x0), dy = Math.round(e.clientY - drag.y0);
    if (!dx && !dy && !drag.moved) return;
    drag.moved = true;
    var mode = drag.mode, x = a.x, y = a.y, w = a.w, h = a.h;
    if (mode === "drag") { x = a.x + dx; y = a.y + dy; }
    else if (one.t === "image" && mode.length === 2) {
      // Una esquina de una foto: crece o encoge sin deformarse.
      var ratio = a.w / Math.max(a.h, 1);
      w = Math.max(16, mode.indexOf("e") >= 0 ? a.w + dx : a.w - dx);
      h = Math.max(16, Math.round(w / ratio));
      if (mode.indexOf("w") >= 0) x = a.x + a.w - w;
      if (mode.indexOf("n") >= 0) y = a.y + a.h - h;
    } else {
      if (mode.indexOf("e") >= 0) w = a.w + dx;
      if (mode.indexOf("s") >= 0) h = a.h + dy;
      if (mode.indexOf("w") >= 0) { x = a.x + dx; w = a.w - dx; }
      if (mode.indexOf("n") >= 0) { y = a.y + dy; h = a.h - dy; }
    }
    w = Math.max(16, w); h = Math.max(16, h);
    var fit = mode === "drag" ? snap(drag.i, x, y, w, h) : { x: x, y: y, lines: [] };
    one.x = clamp(Math.round(fit.x), 0, W - Math.min(w, W));
    one.y = clamp(Math.round(fit.y), 0, L.maxHeight - Math.min(h, L.maxHeight));
    one.w = Math.min(w, W - one.x);
    one.h = Math.min(h, L.maxHeight - one.y);
    if (one.t === "image" && one.fit) delete one.fit;
    // La hoja crece mientras se arrastra hacia abajo.
    if (one.y + one.h > doc.h) {
      doc.h = one.y + one.h;
      if (sheet) sheet.style.height = doc.h + "px";
    }
    var el = sheet && sheet.querySelector('[data-item="' + drag.i + '"]');
    if (el) {
      paintItem(el, one);
      var bad = badOnes();
      Array.prototype.forEach.call(sheet.querySelectorAll(".cv-item"), function (other) {
        other.classList.toggle("is-bad", !!bad[+other.getAttribute("data-item")]);
      });
    }
    if (sheet) guides(sheet, fit.lines);
  });

  function endDrag() {
    if (!drag) return;
    var was = drag;
    drag = null;
    if (was.moved) {
      if (was.mode !== "grip" && was.mode !== "drag") fitText(was.i);
      render(); commit();
    }
  }
  window.addEventListener("pointerup", endDrag);
  window.addEventListener("pointercancel", endDrag);

  /* --------------------------------------------------------- escribir texto */

  stage.addEventListener("dblclick", function (e) {
    var el = e.target.closest(".cv-item--text");
    if (!el) return;
    sel = +el.getAttribute("data-item");
    Array.prototype.forEach.call(el.querySelectorAll(".cv-handle"), function (h) { h.remove(); });
    try { el.contentEditable = "plaintext-only"; } catch (err) { el.contentEditable = "true"; }
    if (el.contentEditable !== "plaintext-only") el.contentEditable = "true";
    el.classList.add("is-editing");
    editing = el;
    el.focus();
    var range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    var picked = window.getSelection();
    picked.removeAllRanges();
    picked.addRange(range);
  });

  stage.addEventListener("paste", function (e) {
    if (!editing) return;
    e.preventDefault();
    var text = (e.clipboardData || window.clipboardData).getData("text/plain");
    document.execCommand("insertText", false, text);
  });

  stage.addEventListener("input", function (e) {
    if (!editing || e.target !== editing || sel === null) return;
    var one = item();
    if (!one) return;
    one.text = editing.innerText.replace(/\n$/, "");
    var need = Math.ceil(editing.scrollHeight);
    if (need > one.h) {
      one.h = Math.min(need, L.maxHeight - one.y);
      editing.style.height = one.h + "px";
      if (one.y + one.h > doc.h) {
        doc.h = one.y + one.h;
        stage.querySelector(".cv-sheet").style.height = doc.h + "px";
      }
    }
  });

  stage.addEventListener("focusout", function (e) {
    if (!editing || e.target !== editing) return;
    var i = sel;
    editing.contentEditable = "false";
    editing = null;
    if (i !== null) fitText(i);
    render(); commit();
  });

  /* Las columnas: a donde está el cursor del texto que se escribe, o al campo
     de la barra que lo tuvo último (el texto del botón, por ejemplo). */
  var marks = root.querySelector("[data-canvas-marks]");
  if (marks) {
    // Sin esto el clic le quita el cursor al texto antes de poder escribir.
    marks.addEventListener("mousedown", function (e) {
      if (e.target.closest("[data-mark]")) e.preventDefault();
    });
    marks.addEventListener("click", function (e) {
      var b = e.target.closest("[data-mark]");
      if (!b) return;
      var mark = b.getAttribute("data-mark");
      if (editing) {
        editing.focus();
        document.execCommand("insertText", false, mark);
        return;
      }
      if (lastField && item()) {
        var start = lastField.selectionStart, end = lastField.selectionEnd;
        if (start === null || start === undefined) lastField.value += mark;
        else lastField.value = lastField.value.slice(0, start) + mark + lastField.value.slice(end);
        lastField.dispatchEvent(new Event("input", { bubbles: true }));
        return;
      }
      say(S.marksNeed);
    });
  }

  /* ------------------------------------------------------------ la barra */

  props.addEventListener("focusin", function (e) {
    if (e.target.matches('input[type="text"], input[type="url"]')) lastField = e.target;
  });

  props.addEventListener("input", function (e) {
    var page = e.target.closest("[data-page-bg]");
    if (page) {
      doc.bg = page.value.toUpperCase();
      var sheet = stage.querySelector(".cv-sheet");
      if (sheet) sheet.style.backgroundColor = doc.bg;
      commitSoon();
      return;
    }
    var input = e.target.closest("[data-prop]");
    var one = item();
    if (!input || !one) return;
    var name = input.getAttribute("data-prop");
    var value = input.type === "checkbox" ? input.checked : input.value;
    if (name === "size" || name === "radius") {
      value = parseInt(value, 10);
      if (isNaN(value)) return;
      if (name === "size") value = clamp(value, L.minSize, L.maxSize);
    }
    if (name === "line") value = parseFloat(value);
    if (name === "bg" || name === "color") value = String(value).toUpperCase();
    one[name] = value;
    if (one.t === "text") fitText(sel);
    var el = stage.querySelector('[data-item="' + sel + '"]');
    if (el && name === "text") el.firstChild ? (el.firstChild.nodeValue = value) : (el.textContent = value);
    if (el) paintItem(el, one);
    // El enlace de una foto cambia lo que se puede encimar: se repinta.
    if (name === "href" && one.t === "image") render();
    commitSoon();
  });

  props.addEventListener("change", function () { render(); });

  props.addEventListener("click", function (e) {
    var b = e.target.closest("[data-action]");
    var one = item();
    if (!b || !one) return;
    var what = b.getAttribute("data-action");
    var list = doc.items;
    if (what === "delete") {
      list.splice(sel, 1);
      sel = null;
    } else if (what === "replace") {
      pickImage(sel);
      return;
    } else if (what === "full") {
      // Todo el ancho, con la proporción de la foto (o la de su caja, en las
      // que se guardaron antes de que se anotara).
      var r = one.r || (one.w / Math.max(one.h, 1));
      one.x = 0; one.w = W;
      if (one.t === "image") { one.h = Math.max(16, Math.round(W / r)); delete one.fit; }
      one.y = Math.min(one.y, L.maxHeight - one.h);
      grow();
    } else if (what === "front" || what === "back") {
      // Solo entre fotos y rectángulos: los textos y botones siempre van
      // delante.
      var backs = [];
      list.forEach(function (x, k) { if (BACK[x.t]) backs.push(k); });
      var at = backs.indexOf(sel);
      var to = what === "front" ? backs[at + 1] : backs[at - 1];
      if (to === undefined) return;
      var tmp = list[to]; list[to] = list[sel]; list[sel] = tmp;
      sel = to;
    }
    render(); commit();
  });

  /* ---------------------------------------------------------------- teclas */

  document.addEventListener("keydown", function (e) {
    var typing = e.target.closest && e.target.closest("input, select, textarea, [contenteditable=true], [contenteditable=plaintext-only]");
    if (editing && e.key === "Escape") { editing.blur(); return; }
    if ((e.ctrlKey || e.metaKey) && !typing) {
      var k = e.key.toLowerCase();
      if (k === "z" && !e.shiftKey) { e.preventDefault(); undo(); return; }
      if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); redo(); return; }
    }
    if (typing || !item()) return;
    var one = item(), step = e.shiftKey ? 10 : 1;
    if (e.key === "Delete" || e.key === "Backspace") {
      doc.items.splice(sel, 1); sel = null; render(); commit(); e.preventDefault(); return;
    }
    if (e.key === "Escape") { sel = null; render(); return; }
    var moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!moves[e.key]) return;
    e.preventDefault();
    one.x = clamp(one.x + moves[e.key][0], 0, W - one.w);
    one.y = clamp(one.y + moves[e.key][1], 0, L.maxHeight - one.h);
    grow();
    render(); commitSoon();
  });

  root.addEventListener("click", function (e) {
    var b = e.target.closest("[data-add]");
    if (b) add(b.getAttribute("data-add"));
  });
  document.querySelector("[data-undo]").addEventListener("click", undo);
  document.querySelector("[data-redo]").addEventListener("click", redo);

  /* ------------------------------------------------ guardar y vista previa */

  saveForm.addEventListener("submit", function (e) {
    if (editing) editing.blur();
    var bad = badOnes();
    if (Object.keys(bad).length) {
      e.preventDefault();
      say(Object.keys(bad).some(function (k) { return bad[k] === "overlap"; }) ? S.overlap : S.linkOverlap);
      return;
    }
    if (checkBlocked) { e.preventDefault(); return; }
    if (!saveForm.querySelector("#nombre").value.trim()) {
      e.preventDefault(); say(S.nameNeeded); saveForm.querySelector("#nombre").focus(); return;
    }
    saveForm.querySelector("[name=lienzo]").value = JSON.stringify(doc);
    dirty = false;
  });

  /* La barra de peso y la revisión antispam. Las pide al servidor, que hace
     la misma cuenta que al guardar; mientras haya un motivo, Guardar no se
     deja pulsar. */
  var check = document.querySelector("[data-canvas-check]");
  var saveButton = saveForm.querySelector("button[type=submit]");
  var checkBlocked = false;
  function runCheck() {
    if (!check) return;
    var body = new FormData();
    body.append("csrf_token", saveForm.querySelector("[name=csrf_token]").value);
    body.append("lienzo", JSON.stringify(doc));
    fetch(root.getAttribute("data-review"), { method: "POST", body: body, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (answer) {
        var share = Math.min(1, answer.bytes / Math.max(answer.max, 1));
        var fill = check.querySelector("[data-meter-fill]");
        fill.style.width = (share * 100).toFixed(1) + "%";
        fill.className = share > 0.9 ? "is-full" : (share > 0.7 ? "is-high" : "");
        check.querySelector("[data-meter-text]").textContent =
          S.meterOf.replace("{kb}", Math.ceil(answer.bytes / 1024))
                   .replace("{max}", Math.round(answer.max / 1024));
        var list = check.querySelector("[data-check-list]");
        list.textContent = "";
        (answer.issues || []).forEach(function (text) {
          var li = document.createElement("li");
          li.textContent = text;
          list.appendChild(li);
        });
        checkBlocked = !answer.ok;
        check.querySelector("[data-check-bad]").hidden = answer.ok;
        check.querySelector("[data-check-ok]").hidden = !answer.ok;
        saveButton.disabled = checkBlocked;
        saveButton.classList.toggle("btn--off", checkBlocked);
      })
      .catch(function () { /* sin revisión no se bloquea: el servidor revisa igual */ });
  }

  /* Con quién se ve: los nombres de las columnas, o los datos de un contacto. */
  var person = document.querySelector("[data-preview-contact]");
  function sendPreview() {
    previewForm.querySelector("[name=lienzo]").value = JSON.stringify(doc);
    previewForm.querySelector("[name=contacto]").value = person ? person.value : "";
    previewForm.submit();
  }
  if (person) person.addEventListener("change", sendPreview);

  var previewTimer = null;
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      sendPreview();
      runCheck();
    }, 800);
  }

  window.addEventListener("beforeunload", function (e) {
    if (!dirty) return;
    e.preventDefault();
    e.returnValue = S.leave;
  });

  /* Las fotos guardadas antes de que se anotara su proporción la leen de la
     imagen. Las que iban «completas» dentro de una caja más grande se
     ajustan a lo que se ve: la caja abraza la foto. */
  function learnRatios() {
    doc.items.forEach(function (one) {
      if (one.t !== "image" || (one.r && one.fit !== "contain")) return;
      var probe = new Image();
      probe.onload = function () {
        var r = probe.naturalWidth / Math.max(probe.naturalHeight, 1);
        one.r = Math.round(r * 10000) / 10000;
        if (one.fit === "contain") {
          var w = Math.min(one.w, Math.round(one.h * r)), h = Math.round(w / r);
          one.x += Math.round((one.w - w) / 2);
          one.y += Math.round((one.h - h) / 2);
          one.w = w; one.h = h;
          delete one.fit;
          render();
        }
        past[past.length - 1] = JSON.stringify(doc);
        if (!dirty) saved = JSON.stringify(doc);
      };
      probe.src = "/img/" + encodeURIComponent(one.name);
    });
  }

  grow();
  render();
  past.push(JSON.stringify(doc));
  learnRatios();
  schedulePreview();
})();
