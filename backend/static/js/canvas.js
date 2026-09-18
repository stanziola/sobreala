/* El lienzo de «Crear plantilla». Sin librerías: la cabecera del panel solo deja
   cargar guiones propios.

   El lienzo es un objeto en memoria ({slides: [{h, bg, items: [...]}]}) que se
   dibuja entero cada vez que cambia. Guardar lo manda en un campo escondido y el
   servidor lo vuelve a revisar todo (services/canvas.py): nada de lo que se
   comprueba aquí es una garantía, solo una ayuda para no perder el trabajo.

   Las imágenes van siempre atrás y los textos y botones delante: así es como
   llega el correo, con las imágenes fundidas en el fondo. */
(function () {
  "use strict";

  var root = document.querySelector("[data-canvas]");
  if (!root) return;

  var S = JSON.parse(root.getAttribute("data-strings") || "{}");
  var L = JSON.parse(root.getAttribute("data-limits") || "{}");
  var FONTS = JSON.parse(document.getElementById("canvas-fonts").textContent || "{}");
  var doc = JSON.parse(document.getElementById("canvas-doc").textContent || "{}");
  if (!doc.slides || !doc.slides.length) doc = { slides: [{ h: 400, bg: "#FFFFFF", items: [] }] };

  var W = L.width || 600;
  var SNAP = 6;
  var FRONT = { text: true, button: true };

  var stage = root.querySelector("[data-stage]");
  var props = root.querySelector("[data-props]");
  var warn = root.querySelector("[data-canvas-warn]");
  var fileInput = root.querySelector("[data-canvas-file]");
  var errorBox = document.querySelector("[data-canvas-error]");
  var saveForm = document.querySelector("[data-canvas-save]");
  var previewForm = document.querySelector("[data-canvas-preview]");

  var sel = null;          // {s: slide index, i: item index} o null
  var slideOn = 0;         // la diapositiva donde se agrega
  var editing = null;      // el elemento de texto que se está escribiendo
  var lastField = null;    // el último campo de la barra que tuvo el cursor
  var dirty = false;
  var past = [], future = [];
  var saved = JSON.stringify(doc);

  /* ------------------------------------------------------------ utilidades */

  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function item() { return sel ? doc.slides[sel.s].items[sel.i] : null; }
  function linePx(one) { return Math.round(one.size * (one.line || 1.4)); }

  function say(text) {
    if (!errorBox) return;
    errorBox.textContent = text || "";
    errorBox.hidden = !text;
  }

  function touch(a, b) {
    return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  }

  function overlapsIn(slide) {
    var bad = {};
    slide.items.forEach(function (a, i) {
      if (!FRONT[a.t]) return;
      slide.items.forEach(function (b, j) {
        if (j <= i || !FRONT[b.t]) return;
        if (touch(a, b)) { bad[i] = true; bad[j] = true; }
      });
    });
    return bad;
  }

  function fewWords(slide) {
    var image = false, words = 0;
    slide.items.forEach(function (one) {
      if (one.t === "image") image = true;
      else words += (one.text || "").split(/\s+/).filter(Boolean).length;
    });
    return image && words < 5;
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

  function render() {
    // Vaciar el lienzo acorta la página un instante y el navegador salta de
    // posición: el segundo clic de un doble clic caería en otra cosa. Se
    // sostiene la altura y se vuelve a donde estaba.
    var scrollY = window.scrollY;
    stage.style.minHeight = stage.offsetHeight + "px";
    stage.textContent = "";
    var anyOverlap = false, anyFew = false;
    doc.slides.forEach(function (slide, s) {
      var wrap = document.createElement("section");
      wrap.className = "cv-wrap" + (s === slideOn ? " is-on" : "");

      var bar = document.createElement("div");
      bar.className = "cv-bar";
      var title = document.createElement("span");
      title.className = "cv-bar__title";
      title.textContent = (S.slide || "{n}").replace("{n}", s + 1);
      bar.appendChild(title);
      var bg = document.createElement("label");
      bg.className = "cv-bar__bg";
      bg.textContent = S.slideBg + " ";
      var picker = document.createElement("input");
      picker.type = "color";
      picker.value = slide.bg;
      picker.setAttribute("data-slide-bg", s);
      bg.appendChild(picker);
      bar.appendChild(bg);
      // El tamaño: los listos y el alto a mano. El ancho es siempre el de un
      // correo, 600.
      var size = document.createElement("label");
      size.className = "cv-bar__bg";
      size.textContent = S.size + " ";
      var pick = document.createElement("select");
      pick.setAttribute("data-slide-size", s);
      [["", S.sizeCustom], ["200", S.sizeBanner], ["600", S.sizeSquare], ["900", S.sizeTall]]
        .forEach(function (pair) {
          var o = document.createElement("option");
          o.value = pair[0];
          o.textContent = pair[1];
          if (String(slide.h) === pair[0]) o.selected = true;
          pick.appendChild(o);
        });
      size.appendChild(pick);
      bar.appendChild(size);
      var tall = document.createElement("label");
      tall.className = "cv-bar__bg";
      tall.textContent = S.height + " ";
      var number = document.createElement("input");
      number.type = "number";
      number.min = L.minHeight;
      number.max = L.maxHeight;
      number.step = 10;
      number.value = slide.h;
      number.className = "cv-bar__h";
      number.setAttribute("data-slide-h", s);
      tall.appendChild(number);
      bar.appendChild(tall);

      [["up", S.slideUp], ["down", S.slideDown], ["copy", S.slideCopy], ["delete", S.slideDelete]]
        .forEach(function (pair) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "btn btn--small btn--outline";
          b.textContent = pair[1];
          b.setAttribute("data-slide-op", pair[0]);
          b.setAttribute("data-slide", s);
          bar.appendChild(b);
        });
      wrap.appendChild(bar);

      var box = document.createElement("div");
      box.className = "cv-slide";
      box.setAttribute("data-slide", s);
      box.style.width = W + "px";
      box.style.height = slide.h + "px";
      box.style.backgroundColor = slide.bg;

      var bad = overlapsIn(slide);
      slide.items.forEach(function (one, i) {
        var el = document.createElement("div");
        el.className = "cv-item cv-item--" + one.t;
        el.setAttribute("data-item", i);
        if (bad[i]) { el.className += " is-bad"; anyOverlap = true; }
        if (sel && sel.s === s && sel.i === i) el.className += " is-sel";
        if (one.t !== "image") el.textContent = one.text;
        paintItem(el, one);
        if (sel && sel.s === s && sel.i === i) {
          ["nw", "ne", "sw", "se"].forEach(function (corner) {
            var h = document.createElement("span");
            h.className = "cv-handle cv-handle--" + corner;
            h.setAttribute("data-handle", corner);
            el.appendChild(h);
          });
        }
        box.appendChild(el);
      });
      wrap.appendChild(box);

      var grip = document.createElement("div");
      grip.className = "cv-grip";
      grip.title = S.resizeSlide;
      grip.setAttribute("data-grip", s);
      wrap.appendChild(grip);

      if (fewWords(slide)) anyFew = true;
      stage.appendChild(wrap);
    });

    var notes = [];
    if (anyOverlap) notes.push(S.overlap);
    if (anyFew) notes.push(S.few);
    warn.textContent = notes.join(" ");
    warn.hidden = !notes.length;
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
    if (!one) return;
    Array.prototype.forEach.call(props.querySelectorAll("[data-only]"), function (el) {
      el.hidden = el.getAttribute("data-only") !== kind;
    });
    Array.prototype.forEach.call(props.querySelectorAll("[data-prop]"), function (input) {
      var name = input.getAttribute("data-prop");
      if (!(name in one)) return;
      if (input === document.activeElement) return;
      if (input.type === "checkbox") input.checked = !!one[name];
      else input.value = String(one[name]);
    });
  }

  /* Un texto crece para que quepa lo escrito: así el correo no lo corta. */
  function fitText(s, i) {
    var one = doc.slides[s].items[i];
    if (!one || one.t !== "text") return;
    var probe = document.createElement("div");
    probe.className = "cv-item cv-item--text cv-probe";
    probe.textContent = one.text || " ";
    paintItem(probe, one);
    probe.style.height = "auto";
    stage.appendChild(probe);
    var need = Math.ceil(probe.scrollHeight);
    stage.removeChild(probe);
    var room = doc.slides[s].h - one.y;
    if (need > one.h) one.h = Math.min(need, room);
  }

  /* ------------------------------------------------------------ agregar */

  function freeY(slide, h) {
    var bottom = 0;
    slide.items.forEach(function (one) {
      if (FRONT[one.t]) bottom = Math.max(bottom, one.y + one.h);
    });
    var y = bottom ? bottom + 20 : 40;
    return y + h <= slide.h ? y : Math.max(0, slide.h - h);
  }

  function add(kind) {
    say("");
    if (kind === "slide") {
      if (doc.slides.length >= L.maxSlides) { say(S.maxSlides); return; }
      doc.slides.push({ h: 400, bg: "#FFFFFF", items: [] });
      slideOn = doc.slides.length - 1;
      sel = null;
      render(); commit();
      return;
    }
    var slide = doc.slides[slideOn];
    if (slide.items.length >= L.maxItems) { say(S.maxItems); return; }
    if (kind === "image") { pickImage(null); return; }
    var one;
    if (kind === "text") {
      one = { t: "text", x: 40, w: W - 80, h: 34, text: S.newText, font: "Arial",
              size: 22, color: "#18181B", bold: false, italic: false, align: "left", line: 1.4 };
    } else {
      one = { t: "button", x: (W - 200) / 2, w: 200, h: 48, text: S.newButton,
              href: "https://", font: "Arial", size: 16, color: "#FFFFFF", bg: "#31A9E8",
              bold: true, italic: false, align: "center", radius: 8 };
    }
    one.y = freeY(slide, one.h);
    slide.items.push(one);
    sel = { s: slideOn, i: slide.items.length - 1 };
    render(); commit();
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
        if (replacing) {
          doc.slides[replacing.s].items[replacing.i].name = answer.name;
        } else {
          var slide = doc.slides[slideOn];
          // Entra a la mitad y centrada, para que se pueda mover y quepa otra
          // al lado. «Llenar la diapositiva» la pone de fondo completo.
          var w = W / 2;
          var h = Math.min(slide.h, Math.round(w * answer.height / Math.max(answer.width, 1)));
          h = Math.max(h, 16);
          // Atrás de todo: las imágenes van al principio de la lista.
          slide.items.unshift({ t: "image", x: Math.round((W - w) / 2),
                                y: Math.round((slide.h - h) / 2), w: w, h: h,
                                name: answer.name, fit: "cover" });
          sel = { s: slideOn, i: 0 };
        }
        render(); commit();
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

  /* Las líneas a las que se pega: los bordes y el centro de la diapositiva, y
     los bordes y el centro de las demás cajas. */
  function snap(slide, moving, x, y, w, h) {
    var xs = [0, W / 2, W], ys = [0, slide.h / 2, slide.h];
    slide.items.forEach(function (one, i) {
      if (i === moving) return;
      xs.push(one.x, one.x + one.w / 2, one.x + one.w);
      ys.push(one.y, one.y + one.h / 2, one.y + one.h);
    });
    var lines = [];
    function best(pos, size, targets, axis) {
      var edges = [pos, pos + size / 2, pos + size], found = null;
      edges.forEach(function (edge, k) {
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
    var grip = e.target.closest("[data-grip]");
    if (grip) {
      var s = +grip.getAttribute("data-grip");
      var lowest = 0;
      doc.slides[s].items.forEach(function (one) { lowest = Math.max(lowest, one.y + one.h); });
      drag = { mode: "grip", s: s, y0: e.clientY, h0: doc.slides[s].h, min: Math.max(L.minHeight, lowest) };
      e.preventDefault();
      return;
    }
    var box = e.target.closest(".cv-slide");
    if (!box) return;
    var s2 = +box.getAttribute("data-slide");
    var el = e.target.closest(".cv-item");
    if (!el) {
      if (editing) editing.blur();
      sel = null; slideOn = s2;
      render();
      return;
    }
    if (el.isContentEditable) return;
    var i = +el.getAttribute("data-item");
    var handle = e.target.closest("[data-handle]");
    slideOn = s2;
    if (!sel || sel.s !== s2 || sel.i !== i) { sel = { s: s2, i: i }; render(); }
    var one = item();
    // Sin captura del puntero: con ella el doble clic le llegaría al lienzo
    // entero y no al texto. El movimiento se escucha en la ventana.
    // Mover se llama «drag» y no «move»: el tamaño se decide mirando si el
    // modo trae n, s, e u o, y «move» trae una e.
    drag = { mode: handle ? handle.getAttribute("data-handle") : "drag", s: s2, i: i,
             x0: e.clientX, y0: e.clientY, start: clone(one), moved: false };
    e.preventDefault();
  });

  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    if (drag.mode === "grip") {
      var h = clamp(Math.round(drag.h0 + e.clientY - drag.y0), drag.min, L.maxHeight);
      doc.slides[drag.s].h = h;
      var box0 = stage.querySelector('.cv-slide[data-slide="' + drag.s + '"]');
      if (box0) box0.style.height = h + "px";
      drag.moved = true;
      return;
    }
    var slide = doc.slides[drag.s], one = slide.items[drag.i], a = drag.start;
    var dx = Math.round(e.clientX - drag.x0), dy = Math.round(e.clientY - drag.y0);
    if (!dx && !dy && !drag.moved) return;
    drag.moved = true;
    var x = a.x, y = a.y, w = a.w, hh = a.h;
    if (drag.mode === "drag") { x = a.x + dx; y = a.y + dy; }
    if (drag.mode.indexOf("e") >= 0) w = a.w + dx;
    if (drag.mode.indexOf("s") >= 0) hh = a.h + dy;
    if (drag.mode.indexOf("w") >= 0) { x = a.x + dx; w = a.w - dx; }
    if (drag.mode.indexOf("n") >= 0) { y = a.y + dy; hh = a.h - dy; }
    w = Math.max(16, w); hh = Math.max(16, hh);
    var fit = drag.mode === "drag" ? snap(slide, drag.i, x, y, w, hh) : { x: x, y: y, lines: [] };
    one.x = clamp(Math.round(fit.x), 0, W - Math.min(w, W));
    one.y = clamp(Math.round(fit.y), 0, slide.h - Math.min(hh, slide.h));
    one.w = Math.min(w, W - one.x);
    one.h = Math.min(hh, slide.h - one.y);
    var box = stage.querySelector('.cv-slide[data-slide="' + drag.s + '"]');
    var el = box && box.querySelector('[data-item="' + drag.i + '"]');
    if (el) {
      paintItem(el, one);
      var bad = overlapsIn(slide);
      Array.prototype.forEach.call(box.querySelectorAll(".cv-item"), function (other) {
        other.classList.toggle("is-bad", !!bad[+other.getAttribute("data-item")]);
      });
    }
    if (box) guides(box, fit.lines);
  });

  function endDrag() {
    if (!drag) return;
    var was = drag;
    drag = null;
    if (was.moved) {
      if (was.mode !== "grip" && was.mode !== "drag") fitText(was.s, was.i);
      render(); commit();
    }
  }
  window.addEventListener("pointerup", endDrag);
  window.addEventListener("pointercancel", endDrag);

  /* --------------------------------------------------------- escribir texto */

  stage.addEventListener("dblclick", function (e) {
    var el = e.target.closest(".cv-item--text");
    if (!el) return;
    var s = +el.closest(".cv-slide").getAttribute("data-slide");
    var i = +el.getAttribute("data-item");
    sel = { s: s, i: i };
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
    if (!editing || e.target !== editing || !sel) return;
    var one = item();
    if (!one) return;
    one.text = editing.innerText.replace(/\n$/, "");
    var need = Math.ceil(editing.scrollHeight);
    if (need > one.h) {
      one.h = Math.min(need, doc.slides[sel.s].h - one.y);
      editing.style.height = one.h + "px";
    }
  });

  stage.addEventListener("focusout", function (e) {
    if (!editing || e.target !== editing) return;
    var s = sel ? sel.s : null, i = sel ? sel.i : null;
    editing.contentEditable = "false";
    editing = null;
    if (s !== null) fitText(s, i);
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
    one[name] = value;
    if (one.t === "text") fitText(sel.s, sel.i);
    var box = stage.querySelector('.cv-slide[data-slide="' + sel.s + '"]');
    var el = box && box.querySelector('[data-item="' + sel.i + '"]');
    if (el && name === "text") el.firstChild ? (el.firstChild.nodeValue = value) : (el.textContent = value);
    if (el) paintItem(el, one);
    commitSoon();
  });

  props.addEventListener("change", function () { render(); });

  props.addEventListener("click", function (e) {
    var b = e.target.closest("[data-action]");
    var one = item();
    if (!b || !one) return;
    var what = b.getAttribute("data-action");
    var list = doc.slides[sel.s].items;
    if (what === "delete") {
      list.splice(sel.i, 1);
      sel = null;
    } else if (what === "replace") {
      pickImage({ s: sel.s, i: sel.i });
      return;
    } else if (what === "fill") {
      one.x = 0; one.y = 0; one.w = W; one.h = doc.slides[sel.s].h; one.fit = "cover";
    } else if (what === "front" || what === "back") {
      // Solo entre imágenes: los textos y botones siempre van delante.
      var pictures = [];
      list.forEach(function (x, k) { if (x.t === "image") pictures.push(k); });
      var at = pictures.indexOf(sel.i);
      var to = what === "front" ? pictures[at + 1] : pictures[at - 1];
      if (to === undefined) return;
      var tmp = list[to]; list[to] = list[sel.i]; list[sel.i] = tmp;
      sel.i = to;
    }
    render(); commit();
  });

  /* ------------------------------------------------------ las diapositivas */

  stage.addEventListener("click", function (e) {
    var b = e.target.closest("[data-slide-op]");
    if (!b) return;
    var s = +b.getAttribute("data-slide"), op = b.getAttribute("data-slide-op");
    var slides = doc.slides;
    if (op === "up" && s > 0) { slides.splice(s - 1, 0, slides.splice(s, 1)[0]); slideOn = s - 1; }
    else if (op === "down" && s < slides.length - 1) { slides.splice(s + 1, 0, slides.splice(s, 1)[0]); slideOn = s + 1; }
    else if (op === "copy") {
      if (slides.length >= L.maxSlides) { say(S.maxSlides); return; }
      slides.splice(s + 1, 0, clone(slides[s])); slideOn = s + 1;
    } else if (op === "delete") {
      if (slides.length === 1) return;
      if (slides[s].items.length && !window.confirm(S.slideConfirm)) return;
      slides.splice(s, 1); slideOn = Math.max(0, s - 1);
    } else return;
    sel = null;
    render(); commit();
  });

  // El alto de una diapositiva, desde la lista o escrito. Nunca más bajo que
  // lo que tiene dentro: eso cortaría una caja.
  function setHeight(s, value) {
    var lowest = 0;
    doc.slides[s].items.forEach(function (one) { lowest = Math.max(lowest, one.y + one.h); });
    var h = clamp(Math.round(value) || 0, Math.max(L.minHeight, lowest), L.maxHeight);
    doc.slides[s].h = h;
    render(); commit();
  }
  stage.addEventListener("change", function (e) {
    var pick = e.target.closest("[data-slide-size]");
    if (pick && pick.value) setHeight(+pick.getAttribute("data-slide-size"), +pick.value);
    var number = e.target.closest("[data-slide-h]");
    if (number) setHeight(+number.getAttribute("data-slide-h"), +number.value);
  });

  stage.addEventListener("input", function (e) {
    var picker = e.target.closest("[data-slide-bg]");
    if (!picker) return;
    var s = +picker.getAttribute("data-slide-bg");
    doc.slides[s].bg = picker.value.toUpperCase();
    var box = stage.querySelector('.cv-slide[data-slide="' + s + '"]');
    if (box) box.style.backgroundColor = picker.value;
    commitSoon();
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
    var one = item(), slide = doc.slides[sel.s], step = e.shiftKey ? 10 : 1;
    if (e.key === "Delete" || e.key === "Backspace") {
      slide.items.splice(sel.i, 1); sel = null; render(); commit(); e.preventDefault(); return;
    }
    if (e.key === "Escape") { sel = null; render(); return; }
    var moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!moves[e.key]) return;
    e.preventDefault();
    one.x = clamp(one.x + moves[e.key][0], 0, W - one.w);
    one.y = clamp(one.y + moves[e.key][1], 0, slide.h - one.h);
    render(); commitSoon();
  });

  root.querySelector("[data-add]") && root.addEventListener("click", function (e) {
    var b = e.target.closest("[data-add]");
    if (b) add(b.getAttribute("data-add"));
  });
  document.querySelector("[data-undo]").addEventListener("click", undo);
  document.querySelector("[data-redo]").addEventListener("click", redo);

  /* ------------------------------------------------ guardar y vista previa */

  saveForm.addEventListener("submit", function (e) {
    if (editing) editing.blur();
    var anyBad = doc.slides.some(function (slide) { return Object.keys(overlapsIn(slide)).length; });
    if (anyBad) { e.preventDefault(); say(S.overlap); return; }
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

  var previewTimer = null;
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      previewForm.querySelector("[name=lienzo]").value = JSON.stringify(doc);
      previewForm.submit();
      runCheck();
    }, 800);
  }

  window.addEventListener("beforeunload", function (e) {
    if (!dirty) return;
    e.preventDefault();
    e.returnValue = S.leave;
  });

  render();
  past.push(JSON.stringify(doc));
  schedulePreview();
})();
