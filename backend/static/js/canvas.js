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
  // Los puntos de cada figura, en fracciones de su caja: los mismos que pinta
  // el correo (`canvas.shape_points()`).
  var SHAPE_POINTS = JSON.parse((document.getElementById("canvas-shapes") || {}).textContent || "{}");
  var doc = JSON.parse(document.getElementById("canvas-doc").textContent || "{}");
  if (!doc.items) doc = { v: 2, h: 600, bg: "#FFFFFF", items: [] };

  var W = L.width || 600;
  var SNAP = 6;
  var FRONT = { text: true, button: true };
  var BACK = { image: true, shape: true };
  // El aire de arriba con el que entra lo que se inserta, y el escalón de la
  // cascada cuando entran varios seguidos.
  var GAP = 20;

  var stage = root.querySelector("[data-stage]");
  // La hoja va dentro de una caja que se desplaza y de otra que mide lo que
  // ocupa con el zoom (octubre de 2026): la hoja mide 600 px de verdad y la
  // vista la acerca o la aleja.
  var scroller = root.querySelector("[data-scroll]");
  var zoomBox = root.querySelector("[data-zoom-box]");
  var props = root.querySelector("[data-props]");
  var warn = root.querySelector("[data-canvas-warn]");
  var fileInput = root.querySelector("[data-canvas-file]");
  var errorBox = document.querySelector("[data-canvas-error]");
  var saveForm = document.querySelector("[data-canvas-save]");
  // El nombre y Guardar viven en la barra, fuera del formulario, y lo nombran
  // con `form` (octubre de 2026).
  var nameField = document.getElementById("nombre");
  var previewForm = document.querySelector("[data-canvas-preview]");

  var picked = [];         // los índices elegidos, que pueden ser varios
  var sel = null;          // el único elegido, o null si son varios o ninguno
  var bench = null;        // lo último copiado, si el portapapeles no deja leer
  var cropping = null;     // el índice de la foto que se está recortando
  var editing = null;      // el elemento de texto que se está escribiendo
  var lastField = null;    // el último campo de la barra que tuvo el cursor
  var dirty = false;
  var past = [], future = [];
  var saved = JSON.stringify(doc);
  var zoom = 1;            // la vista: 1 es la hoja a su tamaño
  var zoomAuto = true;     // si sigue «Ajustar», que cambia con la ventana

  /* ------------------------------------------------------------ utilidades */

  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function item() { return sel === null ? null : doc.items[sel] || null; }
  function linePx(one) { return Math.round(one.size * (one.line || 1.4)); }
  // La columna de la viñeta: la misma cuenta que `canvas.dot_px()` en el correo.
  function dotPx(one) { return Math.round(one.size * 1.2); }
  function isLine(one) { return one && one.t === "shape" && one.shape === "line"; }

  /* ---------------------------------------------------------- lo elegido */

  /* Todo pasa por aquí: `sel` es lo elegido cuando es uno solo, que es como
     funciona la barra de propiedades, y `picked` es la lista. */
  function pick(what) {
    // Elegir otra cosa cierra el recorte: el recuadro es de esa foto.
    if (cropping !== null && (what === null || what === undefined || what !== cropping)) {
      cropping = null;
    }
    var list = what === null || what === undefined ? []
      : (typeof what === "number" ? [what] : what.slice());
    picked = list.filter(function (i, at) {
      return doc.items[i] && list.indexOf(i) === at;
    });
    sel = picked.length === 1 ? picked[0] : null;
  }

  function isPicked(i) { return picked.indexOf(i) >= 0; }
  function chosen() { return picked.map(function (i) { return doc.items[i]; }); }

  /* Un elemento arrastra a su grupo: agrupar es para moverlos juntos. */
  function tied(i) {
    var one = doc.items[i];
    if (!one || !one.g) return [i];
    var out = [];
    doc.items.forEach(function (x, k) { if (x.g === one.g) out.push(k); });
    return out;
  }

  /* La caja que abarca a varios, para moverlos y alinearlos como uno. */
  function around(list) {
    var x = Math.min.apply(null, list.map(function (o) { return o.x; }));
    var y = Math.min.apply(null, list.map(function (o) { return o.y; }));
    return { x: x, y: y,
             w: Math.max.apply(null, list.map(function (o) { return o.x + o.w; })) - x,
             h: Math.max.apply(null, list.map(function (o) { return o.y + o.h; })) - y };
  }

  function say(text) {
    if (!errorBox) return;
    errorBox.textContent = text || "";
    errorBox.hidden = !text;
  }

  /* Lo que ocupa de verdad: su caja, o la que abarca su giro. La caja que se
     arrastra no cambia al girar; la huella sí, y es la que decide qué se
     encima con qué. Es la misma cuenta que hace services/canvas.py. */
  function bounds(one) {
    var angle = one.rot || 0;
    if (!angle) return one;
    var rad = angle * Math.PI / 180;
    var cos = Math.abs(Math.cos(rad)), sin = Math.abs(Math.sin(rad));
    var w = Math.round(one.w * cos + one.h * sin);
    var h = Math.round(one.w * sin + one.h * cos);
    return { x: Math.round(one.x + (one.w - w) / 2),
             y: Math.round(one.y + (one.h - h) / 2), w: w, h: h };
  }

  function touch(a, b) {
    a = bounds(a); b = bounds(b);
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
    doc.items.forEach(function (one) {
      var b = bounds(one);
      bottom = Math.max(bottom, b.y + b.h);
    });
    return bottom;
  }

  /* Lo girado ocupa más: se empuja hacia dentro para que quepa en la hoja, que
     es lo que el servidor exige al guardar. */
  function fitRot(one) {
    if (!one || !one.rot) return;
    var b = bounds(one);
    if (b.x < 0) one.x -= b.x;
    if (b.y < 0) one.y -= b.y;
    b = bounds(one);
    if (b.x + b.w > W) one.x -= (b.x + b.w - W);
    if (one.x < 0) one.x = 0;
    b = bounds(one);
    if (b.y + b.h > doc.h) one.y -= (b.y + b.h - doc.h);
    if (one.y < 0) one.y = 0;
  }

  /* La hoja **no crece sola**: su alto solo cambia con el tirador de abajo,
     con el contador de la barra o con «Ajustar al contenido». Lo que se
     inserta entra arriba y se acomoda a mano, lo que se arrastra topa con el
     borde, y un texto que ya no cabe se queda cortado y se avisa. */

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
    pick(null); editing = null;
    render(); schedulePreview();
  }

  function redo() {
    if (!future.length) return;
    var next = future.pop();
    past.push(next);
    doc = JSON.parse(next);
    pick(null); editing = null;
    render(); schedulePreview();
  }

  /* ------------------------------------------------------------- dibujar */

  function paintItem(el, one) {
    el.style.left = one.x + "px";
    el.style.top = one.y + "px";
    el.style.width = one.w + "px";
    el.style.height = one.h + "px";
    // Gira sobre su centro, como lo hornea el servidor al armar el correo.
    el.style.transform = one.rot ? "rotate(" + one.rot + "deg)" : "";
    if (one.t === "image") {
      el.style.backgroundImage = "url('/img/" + encodeURIComponent(one.name) + "')";
      var cut = one.crop;
      if (cut) {
        // El pedazo elegido llena la caja. El recuadro guarda la proporción de
        // la caja, así que llenarla no deforma nada: es lo mismo que hace el
        // servidor al armar el correo.
        el.style.backgroundSize = (100 / cut[2]).toFixed(2) + "% " + (100 / cut[3]).toFixed(2) + "%";
        el.style.backgroundPosition =
          (cut[2] < 1 ? cut[0] / (1 - cut[2]) * 100 : 0).toFixed(2) + "% " +
          (cut[3] < 1 ? cut[1] / (1 - cut[3]) * 100 : 0).toFixed(2) + "%";
      } else {
        el.style.backgroundSize = one.fit === "contain" ? "contain" : "cover";
        el.style.backgroundPosition = "";
      }
      // Su forma o sus esquinas, y su borde (octubre de 2026). Los tiradores
      // viven en otra capa, así que recortar la caja no los recorta.
      el.style.clipPath = one.mask ? (one.mask === "ellipse" ? "ellipse(50% 50% at 50% 50%)"
                                                             : CLIPS[one.mask] || "") : "";
      el.style.borderRadius = !one.mask && one.radius ? one.radius + "px" : "";
      paintEdge(el, one.mask || "rect", one);
      return;
    }
    if (one.t === "shape") {
      // El color va en un hijo y no en la caja: el recorte de las figuras
      // (`clip-path`) también recortaría los tiradores, que son hijos suyos.
      var fill = el.querySelector(".cv-fill");
      if (!fill) {
        fill = document.createElement("span");
        fill.className = "cv-fill";
        el.insertBefore(fill, el.firstChild);
      }
      fill.style.backgroundColor = one.bg;
      // Un círculo es su caja redondeada del todo; un óvalo, si no es cuadrada.
      fill.style.borderRadius = one.shape === "ellipse" ? "50%" : one.radius + "px";
      fill.style.clipPath = CLIPS[one.shape] || "";
      paintEdge(el, one.shape === "line" ? "rect" : one.shape, one);
      return;
    }
    el.style.fontFamily = FONTS[one.font] || FONTS.Arial || "Arial, sans-serif";
    el.style.fontSize = one.size + "px";
    el.style.color = one.color;
    el.style.fontWeight = one.bold ? "bold" : "normal";
    el.style.fontStyle = one.italic ? "italic" : "normal";
    if (one.t === "text") {
      el.style.lineHeight = linePx(one) + "px";
      // Con viñetas va a la izquierda, como en el correo.
      el.style.textAlign = one.list ? "left" : one.align;
      el.style.setProperty("--cv-dot", dotPx(one) + "px");
      el.classList.toggle("cv-item--list", !!one.list);
      // El tipo de viñeta: lo dibuja el CSS (octubre de 2026).
      if (one.list) el.setAttribute("data-bullet", one.list === true ? "dot" : one.list);
      else el.removeAttribute("data-bullet");
    } else {
      el.style.lineHeight = one.h + "px";
      el.style.backgroundColor = one.bg;
      el.style.borderRadius = one.radius + "px";
    }
  }

  /* Lo escrito dentro de su caja. Con viñetas, cada renglón es un bloque con la
     suya delante y sangría francesa, de la misma medida que en el correo: así
     el texto se parte en el mismo sitio en los dos. Un renglón vacío es un
     hueco del alto de una línea. */
  function fillText(el, one) {
    if (one.t !== "text") { el.textContent = one.text; return; }
    el.textContent = "";
    if (!one.list) { fillRuns(el, runsOf(one)); return; }
    linesOf(one).forEach(function (runs) {
      var plain = runs.map(function (r) { return r.text; }).join("");
      var row = document.createElement("div");
      row.className = plain.trim() ? "cv-li" : "cv-li cv-li--blank";
      if (plain.trim()) fillRuns(row, runs); else row.textContent = " ";
      el.appendChild(row);
    });
  }

  /* ------------------------------------------- el formato por palabras */

  /* Un texto puede llevar `runs` (octubre de 2026): tramos con su negrita,
     cursiva, subrayado, color y enlace. Lo de la caja (`bold`, `italic`,
     `color`) es la base, y cada tramo dice solo en qué cambia; así lo guarda
     el servidor (`canvas._runs`). Mientras se escribe, cada tramo es un
     `span`, y al terminar se vuelven a leer de lo escrito. */
  var RUN_KEYS = ["b", "i", "u", "color", "href"];
  var editRange = null;     // lo seleccionado en el texto que se escribe

  function baseOf(one) {
    return { b: !!one.bold, i: !!one.italic, u: false,
             color: String(one.color || "").toUpperCase() };
  }

  function runsOf(one) {
    return one.runs && one.runs.length ? clone(one.runs) : [{ text: one.text || "" }];
  }

  function sameStyle(a, b) {
    return RUN_KEYS.every(function (k) { return a[k] === b[k]; });
  }

  /* Como los guarda el servidor: sin lo que dice lo mismo que la caja y con
     los seguidos iguales unidos. Sin formato no queda ninguno. */
  function tidyRuns(one, runs) {
    var base = baseOf(one), out = [];
    runs.forEach(function (run) {
      if (!run.text) return;
      var r = { text: run.text };
      ["b", "i", "u"].forEach(function (k) {
        if (typeof run[k] === "boolean" && run[k] !== base[k]) r[k] = run[k];
      });
      if (run.color && run.color.toUpperCase() !== base.color) r.color = run.color.toUpperCase();
      if (run.href) r.href = run.href;
      var last = out[out.length - 1];
      if (last && sameStyle(last, r)) last.text += r.text; else out.push(r);
    });
    one.text = out.map(function (r) { return r.text; }).join("");
    if (out.some(function (r) { return Object.keys(r).length > 1; })) one.runs = out;
    else delete one.runs;
  }

  function fillRuns(el, runs) {
    runs.forEach(function (run) {
      var span = document.createElement("span");
      span.textContent = run.text;
      if (run.b !== undefined) span.style.fontWeight = run.b ? "bold" : "normal";
      if (run.i !== undefined) span.style.fontStyle = run.i ? "italic" : "normal";
      if (run.u) span.style.textDecoration = "underline";
      if (run.color) span.style.color = run.color;
      if (run.href) {
        span.setAttribute("data-href", run.href);
        span.className = "cv-link";
        span.title = run.href;
      }
      el.appendChild(span);
    });
  }

  function linesOf(one) {
    var lines = [[]];
    runsOf(one).forEach(function (run) {
      run.text.split("\n").forEach(function (part, at) {
        if (at) lines.push([]);
        if (part) lines[lines.length - 1].push(Object.assign({}, run, { text: part }));
      });
    });
    return lines;
  }

  function toHex(css) {
    var m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(css || "");
    if (!m) return /^#[0-9a-f]{6}$/i.test(css || "") ? css.toUpperCase() : "";
    return "#" + [m[1], m[2], m[3]].map(function (n) {
      var h = (+n).toString(16);
      return h.length < 2 ? "0" + h : h;
    }).join("").toUpperCase();
  }

  /* Los tramos de lo que hay escrito en la caja que se edita. */
  function readRuns(el) {
    var out = [];
    function push(text, st) { if (text) out.push(Object.assign({ text: text }, st)); }
    function walk(node, st) {
      Array.prototype.forEach.call(node.childNodes, function (child) {
        if (child.nodeType === 3) { push(child.nodeValue.replace(/\u00a0/g, " "), st); return; }
        if (child.nodeType !== 1) return;
        var tag = child.tagName;
        if (tag === "BR") { push("\n", st); return; }
        var s = Object.assign({}, st), cs = child.style;
        if (tag === "B" || tag === "STRONG") s.b = true;
        if (tag === "I" || tag === "EM") s.i = true;
        if (tag === "U") s.u = true;
        if (cs.fontWeight) s.b = cs.fontWeight === "bold" || +cs.fontWeight >= 600;
        if (cs.fontStyle) s.i = cs.fontStyle === "italic";
        var deco = cs.textDecorationLine || cs.textDecoration;
        if (deco) s.u = /underline/.test(deco);
        if (cs.color) s.color = toHex(cs.color) || s.color;
        if (child.getAttribute("data-href")) s.href = child.getAttribute("data-href");
        if ((tag === "DIV" || tag === "P") && out.length && !/\n$/.test(out[out.length - 1].text)) {
          push("\n", st);
        }
        walk(child, s);
      });
    }
    walk(el, {});
    if (out.length) out[out.length - 1].text = out[out.length - 1].text.replace(/\n$/, "");
    return out;
  }

  function syncEditing() {
    var one = item();
    if (!editing || !one) return;
    tidyRuns(one, readRuns(editing));
  }

  /* Cuántas letras hay antes de un punto de la caja (un salto cuenta una). */
  function charsTo(el, node, offset) {
    var count = 0, done = false;
    function all(n) {
      if (n.nodeType === 3) count += n.nodeValue.length;
      else if (n.tagName === "BR") count += 1;
      else for (var c = n.firstChild; c; c = c.nextSibling) all(c);
    }
    function walk(n) {
      if (done) return;
      if (n === node) {
        if (n.nodeType === 3) count += offset;
        else for (var k = 0; k < offset && k < n.childNodes.length; k++) all(n.childNodes[k]);
        done = true;
        return;
      }
      if (n.nodeType === 3) { count += n.nodeValue.length; return; }
      if (n.tagName === "BR") { count += 1; return; }
      for (var c = n.firstChild; c && !done; c = c.nextSibling) walk(c);
    }
    if (node === el) { walk(el); return count; }
    for (var c = el.firstChild; c && !done; c = c.nextSibling) walk(c);
    return count;
  }

  function selOffsets(el) {
    var s = window.getSelection();
    if (!el || !s.rangeCount) return null;
    var r = s.getRangeAt(0);
    if (!el.contains(r.startContainer) || !el.contains(r.endContainer)) return null;
    return { start: charsTo(el, r.startContainer, r.startOffset),
             end: charsTo(el, r.endContainer, r.endOffset) };
  }

  function placeSel(el, start, end) {
    function find(target) {
      var count = 0, hit = null;
      (function walk(n) {
        for (var c = n.firstChild; c && !hit; c = c.nextSibling) {
          if (c.nodeType === 3) {
            if (count + c.nodeValue.length >= target) { hit = { node: c, offset: target - count }; return; }
            count += c.nodeValue.length;
          } else if (c.tagName === "BR") {
            if (count + 1 > target) { hit = { node: n, offset: Array.prototype.indexOf.call(n.childNodes, c) }; return; }
            count += 1;
          } else walk(c);
        }
      })(el);
      return hit || { node: el, offset: el.childNodes.length };
    }
    var a = find(start), b = find(end);
    var r = document.createRange();
    r.setStart(a.node, a.offset);
    r.setEnd(b.node, b.offset);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  /* Parte los tramos para que uno empiece justo en `at`; devuelve cuál. */
  function cutRuns(runs, at) {
    var pos = 0;
    for (var k = 0; k < runs.length; k++) {
      var len = runs[k].text.length;
      if (pos === at) return k;
      if (at < pos + len) {
        runs.splice(k, 1, Object.assign({}, runs[k], { text: runs[k].text.slice(0, at - pos) }),
                    Object.assign({}, runs[k], { text: runs[k].text.slice(at - pos) }));
        return k + 1;
      }
      pos += len;
    }
    return runs.length;
  }

  function effective(one, run, key) {
    return run[key] !== undefined ? run[key] : baseOf(one)[key];
  }

  /* Pone `key` en las letras de `start` a `end`; sin valor, lo alterna, y con
     null lo quita. Devuelve lo que puso. */
  function formatRange(one, start, end, key, value) {
    var runs = runsOf(one);
    var a = cutRuns(runs, start), b = cutRuns(runs, end);
    var inside = runs.slice(a, b);
    if (value === undefined) value = !inside.every(function (r) { return effective(one, r, key); });
    inside.forEach(function (r) { if (value === null) delete r[key]; else r[key] = value; });
    tidyRuns(one, runs);
    return value;
  }

  /* Lo que se formatea: lo seleccionado mientras se escribe, o todo el texto. */
  function formatSpan(one) {
    var r = editing ? (selOffsets(editing) || editRange) : null;
    if (r && r.start !== r.end) return { start: Math.min(r.start, r.end), end: Math.max(r.start, r.end), part: true };
    return { start: 0, end: (one.text || "").length, part: false };
  }

  /* Vuelve a escribir la caja que se edita con sus tramos, y deja la
     selección donde estaba. */
  function refillEditing(one, span, focus) {
    if (!editing) return;
    editing.textContent = "";
    fillRuns(editing, runsOf(one));
    if (focus) {
      editing.focus();
      placeSel(editing, span.start, span.end);
    }
    editRange = { start: span.start, end: span.end };
  }

  function applyFormat(key, value, focus) {
    var one = item();
    if (!one || one.t !== "text") return;
    if (editing) syncEditing();
    var span = formatSpan(one);
    formatRange(one, span.start, span.end, key, value);
    if (editing) refillEditing(one, span, focus !== false);
    else { checkFit(); render(); }
    commitSoon();
    showFormat();
  }

  /* Las casillas de negrita, cursiva y subrayado dicen cómo está lo
     seleccionado, o el texto entero. */
  function showFormat() {
    var one = item();
    if (!one || one.t !== "text") return;
    var runs = runsOf(one), span = formatSpan(one), pos = 0, inside = [];
    runs.forEach(function (r) {
      var from = pos, to = pos + r.text.length;
      pos = to;
      if (span.start === span.end ? (from <= span.start && span.start <= to) : (to > span.start && from < span.end)) inside.push(r);
    });
    if (!inside.length) inside = runs;
    var all = function (key) { return inside.every(function (r) { return effective(one, r, key); }); };
    var set = function (sel, on) { var box = props.querySelector(sel); if (box) box.checked = on; };
    set('[data-props-for~="text"] [data-prop="bold"]', all("b"));
    set('[data-props-for~="text"] [data-prop="italic"]', all("i"));
    set("[data-format=u]", all("u"));
  }

  /* El enlace de lo seleccionado o del texto entero (octubre de 2026). */
  var linkMenu = props.querySelector("[data-link-menu]");
  var linkUrl = props.querySelector("[data-link-url]");
  var linkU = props.querySelector("[data-link-u]");
  var linkSpan = null;

  function openLink() {
    var one = item();
    if (!linkMenu || !one || one.t !== "text") return;
    if (editing) syncEditing();
    linkSpan = formatSpan(one);
    var found = runsOf(one).filter(function (r) { return r.href; })[0];
    linkUrl.value = found ? found.href : "";
    linkU.checked = found ? !!found.u : true;
    linkMenu.open = true;
    linkUrl.focus();
  }

  function applyLink(remove) {
    var one = item();
    if (!one || one.t !== "text") return;
    var span = linkSpan || formatSpan(one);
    if (remove) {
      formatRange(one, span.start, span.end, "href", null);
      formatRange(one, span.start, span.end, "u", null);
    } else {
      var url = linkUrl.value.trim();
      if (url && !/^(https:\/\/|mailto:)/i.test(url)) url = "https://" + url.replace(/^(http:\/\/|\/+)/i, "");
      if (!/^(https:\/\/|mailto:)[^\s"'<>]+$/i.test(url)) { say(S.linkBad); linkUrl.focus(); return; }
      say("");
      formatRange(one, span.start, span.end, "href", url);
      formatRange(one, span.start, span.end, "u", linkU.checked);
    }
    linkMenu.open = false;
    linkSpan = null;
    if (editing) refillEditing(one, span, true);
    else { checkFit(); render(); }
    commitSoon();
  }

  if (linkMenu) {
    linkMenu.querySelector("summary").addEventListener("click", function (e) {
      e.preventDefault();
      if (linkMenu.open) { linkMenu.open = false; return; }
      openLink();
    });
    props.querySelector("[data-link-apply]").addEventListener("click", function () { applyLink(false); });
    props.querySelector("[data-link-remove]").addEventListener("click", function () { applyLink(true); });
    linkUrl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); applyLink(false); }
    });
  }

  document.addEventListener("selectionchange", function () {
    if (!editing) return;
    var r = selOffsets(editing);
    if (r) { editRange = r; showFormat(); }
  });

  function endEditing() {
    if (!editing) return;
    syncEditing();
    editing.contentEditable = "false";
    editing = null;
    editRange = null;
    checkFit();
    render(); commit();
  }

  /* Las figuras que el navegador dibuja recortando su caja. Son las mismas
     que `services/canvas.py` pinta con Pillow, para que el editor y el correo
     enseñen lo mismo. */
  var CLIPS = {};
  Object.keys(SHAPE_POINTS).forEach(function (name) {
    CLIPS[name] = "polygon(" + SHAPE_POINTS[name].map(function (p) {
      return (p[0] * 100).toFixed(2) + "% " + (p[1] * 100).toFixed(2) + "%";
    }).join(", ") + ")";
  });

  /* El borde de una foto o de una figura (octubre de 2026): un SVG encima,
     con la misma forma, recortado a ella para que el trazo quede por dentro,
     como lo pinta el correo. */
  var SVGNS = "http://www.w3.org/2000/svg";
  var edgeSeq = 0;

  function shapeNode(figure, w, h, radius) {
    var n;
    if (figure === "ellipse") {
      n = document.createElementNS(SVGNS, "ellipse");
      n.setAttribute("cx", w / 2); n.setAttribute("cy", h / 2);
      n.setAttribute("rx", w / 2); n.setAttribute("ry", h / 2);
    } else if (SHAPE_POINTS[figure]) {
      n = document.createElementNS(SVGNS, "polygon");
      n.setAttribute("points", SHAPE_POINTS[figure].map(function (p) {
        return (p[0] * w) + "," + (p[1] * h);
      }).join(" "));
    } else {
      n = document.createElementNS(SVGNS, "rect");
      n.setAttribute("width", w); n.setAttribute("height", h);
      var r = Math.min(radius || 0, w / 2, h / 2);
      n.setAttribute("rx", r); n.setAttribute("ry", r);
    }
    return n;
  }

  function paintEdge(el, figure, one) {
    var old = el.querySelector(".cv-edge");
    if (old) old.remove();
    if (!one.border) return;
    var svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("class", "cv-edge");
    svg.setAttribute("viewBox", "0 0 " + one.w + " " + one.h);
    svg.setAttribute("preserveAspectRatio", "none");
    var id = "cv-edge-" + (++edgeSeq);
    var defs = document.createElementNS(SVGNS, "defs");
    var clip = document.createElementNS(SVGNS, "clipPath");
    clip.setAttribute("id", id);
    clip.appendChild(shapeNode(figure, one.w, one.h, one.radius));
    defs.appendChild(clip);
    svg.appendChild(defs);
    var line = shapeNode(figure, one.w, one.h, one.radius);
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", one.border_color || "#18181B");
    line.setAttribute("stroke-width", one.border * 2);
    line.setAttribute("clip-path", "url(#" + id + ")");
    svg.appendChild(line);
    el.appendChild(svg);
  }

  // Las fotos y los rectángulos se tiran también de los lados: en una foto,
  // las esquinas guardan su proporción y los lados la recortan.
  var CORNERS = ["nw", "ne", "sw", "se"];
  var SIDES = ["n", "s", "e", "w"];

  /* La flecha que cierra un círculo: sin ella el tirador del giro es un punto
     blanco que no dice qué hace. */
  var TURN_ICON =
    '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" ' +
    'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 3v4h-4"/></svg>';

  /* Los tiradores de lo elegido, en una capa aparte encima de la hoja.

     Dentro del elemento no pueden ir: cada `.cv-item` tiene z-index propio, así
     que es su propio contexto de apilado y sus hijos no se escapan de él. El
     tirador del giro sale 30 px por encima de la caja y quedaba debajo de un
     texto vecino. Subir el elemento elegido lo resolvía, pero entonces una
     figura de atrás saltaba delante de todo al tocarla y el editor dejaba de
     enseñar el orden con el que sale el correo. */
  function chrome(sheet, one, i) {
    var layer = document.createElement("div");
    layer.className = "cv-chrome";
    layer.setAttribute("data-item", i);
    layerBox(layer, one);
    // Una línea solo se alarga de sus puntas: su grosor se escribe en la barra.
    var handles = isLine(one) ? ["e", "w"] : (BACK[one.t] ? CORNERS.concat(SIDES) : CORNERS);
    handles.forEach(function (where) {
      var h = document.createElement("span");
      h.className = "cv-handle cv-handle--" + where;
      h.setAttribute("data-handle", where);
      layer.appendChild(h);
    });
    // El tirador de giro, encima de la caja y solo en lo que gira: las fotos y
    // las figuras. Un texto no gira, que sería volverlo imagen.
    if (BACK[one.t]) {
      var turn = document.createElement("span");
      turn.className = "cv-turn";
      turn.setAttribute("data-turn", "");
      turn.title = S.rotDrag;
      turn.innerHTML = TURN_ICON;
      layer.appendChild(turn);
    }
    sheet.appendChild(layer);
  }

  function layerBox(layer, one) {
    layer.style.left = one.x + "px";
    layer.style.top = one.y + "px";
    layer.style.width = one.w + "px";
    layer.style.height = one.h + "px";
    layer.style.transform = one.rot ? "rotate(" + one.rot + "deg)" : "";
  }

  /* Mientras se arrastra no se vuelve a dibujar la hoja entera: se mueve el
     elemento y, con él, la capa de sus tiradores, que si no se quedaría
     clavada donde estaba. Devuelve el elemento, o null si no está dibujado. */
  function repaint(sheet, one, i) {
    if (!sheet) return null;
    var el = sheet.querySelector('.cv-item[data-item="' + i + '"]');
    if (el) paintItem(el, one);
    var layer = sheet.querySelector('.cv-chrome[data-item="' + i + '"]');
    if (layer) layerBox(layer, one);
    return el;
  }

  function render() {
    // Vaciar el lienzo acorta la página un instante y el navegador salta de
    // posición: el segundo clic de un doble clic caería en otra cosa. Se
    // sostiene la altura y se vuelve a donde estaba.
    var scrollY = scroller ? scroller.scrollTop : window.scrollY;
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
      el.className = "cv-item cv-item--" + one.t + (isLine(one) ? " cv-item--line" : "");
      el.setAttribute("data-item", i);
      if (bad[i]) { el.className += " is-bad"; notes[bad[i]] = true; }
      if (cut[i] === "cut") { el.className += " is-cut"; notes.cut = true; }
      if (cut[i] === "grow") notes.grow = true;
      if (isPicked(i)) el.className += " is-sel";
      if (FRONT[one.t]) fillText(el, one);
      paintItem(el, one);
      sheet.appendChild(el);
    });
    // Los tiradores son para cambiar el tamaño de uno: con varios elegidos
    // no se sabría de cuál.
    if (sel !== null && doc.items[sel]) chrome(sheet, doc.items[sel], sel);
    if (cropping !== null) cropLayer(sheet);
    stage.appendChild(sheet);

    var grip = document.createElement("div");
    grip.className = "cv-grip";
    grip.title = S.resizeSheet;
    grip.setAttribute("data-grip", "");
    stage.appendChild(grip);

    var said = [];
    if (notes.overlap) said.push(S.overlap);
    if (notes.link) said.push(S.linkOverlap);
    if (notes.cut) said.push(S.textCut);
    if (notes.grow) said.push(S.textGrows);
    warn.textContent = said.join(" ");
    warn.hidden = !said.length;
    showProps();
    stage.style.minHeight = "";
    sizeZoom();
    if (scroller) { if (scroller.scrollTop !== scrollY) scroller.scrollTop = scrollY; }
    else if (window.scrollY !== scrollY) window.scrollTo(window.scrollX, scrollY);
  }

  /* -------------------------------------------------------------- el zoom */

  /* La hoja se escala con `transform` y la caja de fuera toma lo que ocupa
     escalada, que es lo que se desplaza. Todo lo que viene del ratón se divide
     entre el zoom (`unzoom`) para volver a medidas de la hoja. */
  var ZOOMS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
  var zoomValue = root.querySelector("[data-zoom-value]");

  function unzoom(px) { return px / zoom; }

  function sizeZoom() {
    if (!zoomBox) return;
    stage.style.transform = zoom === 1 ? "" : "scale(" + zoom + ")";
    zoomBox.style.width = Math.ceil(stage.offsetWidth * zoom) + "px";
    zoomBox.style.height = Math.ceil(stage.offsetHeight * zoom) + "px";
    if (zoomValue) zoomValue.textContent = Math.round(zoom * 100) + "%";
  }

  function setZoom(value, auto) {
    zoom = clamp(Math.round(value * 100) / 100, ZOOMS[0], ZOOMS[ZOOMS.length - 1]);
    zoomAuto = !!auto;
    sizeZoom();
  }

  /* «Ajustar»: la hoja llena el ancho que queda, hasta un 125 %: más grande
     la letra se ve borrosa y se pierde de vista el resto del correo. */
  function fitZoom() {
    if (!scroller) return;
    var room = scroller.clientWidth - 48;
    if (room > 0) setZoom(Math.min(1.25, Math.max(ZOOMS[0], room / (stage.offsetWidth || W))), true);
  }

  function stepZoom(dir) {
    var next = dir > 0 ? ZOOMS.filter(function (z) { return z > zoom + 0.001; })[0]
                       : ZOOMS.filter(function (z) { return z < zoom - 0.001; }).pop();
    if (next) setZoom(next, false);
  }

  var zoomBar = root.querySelector("[data-zoom]");
  if (zoomBar) {
    zoomBar.addEventListener("click", function (e) {
      var step = e.target.closest("[data-zoom-step]");
      if (step) stepZoom(+step.getAttribute("data-zoom-step"));
      if (e.target.closest("[data-zoom-fit]")) fitZoom();
    });
  }
  if (scroller) {
    // Ctrl y la rueda acercan y alejan la hoja, no la página.
    scroller.addEventListener("wheel", function (e) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      stepZoom(e.deltaY < 0 ? 1 : -1);
    }, { passive: false });
  }
  window.addEventListener("resize", function () { if (zoomAuto) fitZoom(); });

  /* ------------------------------------------------- el riel y sus paneles */

  /* Cada ícono abre su panel y el mismo lo cierra. El último abierto se
     recuerda en este navegador. Sin JavaScript se ven todos. */
  var rail = document.querySelector("[data-rail]");
  var panelBox = document.querySelector("[data-panel-box]");
  var PANEL_KEY = "sa_studio_panel";

  function openPanel(name) {
    if (!panelBox) return;
    Array.prototype.forEach.call(panelBox.querySelectorAll("[data-panel-for]"), function (p) {
      p.hidden = p.getAttribute("data-panel-for") !== name;
    });
    panelBox.hidden = !name;
    Array.prototype.forEach.call(rail.querySelectorAll("[data-panel]"), function (b) {
      var on = b.getAttribute("data-panel") === name;
      b.classList.toggle("is-on", on);
      b.setAttribute("aria-expanded", on ? "true" : "false");
    });
    try { localStorage.setItem(PANEL_KEY, name || ""); } catch (err) { /* sin memoria */ }
    if (zoomAuto) requestAnimationFrame(fitZoom);
  }

  if (rail && panelBox) {
    root.classList.add("is-live");
    rail.addEventListener("click", function (e) {
      var b = e.target.closest("[data-panel]");
      if (!b) return;
      var name = b.getAttribute("data-panel");
      openPanel(b.classList.contains("is-on") ? "" : name);
    });
    var first = null;
    try { first = localStorage.getItem(PANEL_KEY); } catch (err) { first = null; }
    if (first === null) first = window.innerWidth > 1100 ? "text" : "";
    if (first && !rail.querySelector('[data-panel="' + first + '"]')) first = "text";
    openPanel(first);
  }

  /* Los menús de «⋯», de Alinear y de Descargar: se cierran al elegir algo y
     al pulsar fuera. */
  document.addEventListener("click", function (e) {
    Array.prototype.forEach.call(document.querySelectorAll(".props__more[open], .studio__more[open]"), function (menu) {
      if (!menu.contains(e.target) || e.target.closest(".props__menu button, .studio__menu-item")) {
        menu.open = false;
      }
    });
  });

  function showProps() {
    var one = item();
    var kind = picked.length > 1 ? "many" : (one ? one.t : "none");
    if (kind === "many") {
      var count = props.querySelector("[data-many-count]");
      if (count) count.textContent = S.many.replace("{n}", picked.length);
    }
    Array.prototype.forEach.call(props.querySelectorAll("[data-props-for]"), function (row) {
      row.hidden = row.getAttribute("data-props-for").split(" ").indexOf(kind) < 0;
    });
    var page = props.querySelector("[data-page-bg]");
    if (page && page !== document.activeElement) page.value = doc.bg;
    var high = props.querySelector("[data-sheet-h]");
    if (high && high !== document.activeElement) high.value = String(doc.h);
    if (!one || kind === "many") return;
    // «data-only» vale para el tipo («button») y para la figura de un
    // rectángulo («shape-ellipse»): el redondeo es del rectángulo y el aviso
    // de la imagen es del círculo.
    var also = kind === "shape" ? "shape-" + (one.shape || "rect") : "";
    // El borde es de las figuras con relleno (no de la línea), y las esquinas
    // de una foto sin forma.
    var extra = kind === "shape" && one.shape !== "line" ? "shape-fill"
              : (kind === "image" && !one.mask ? "image-plain" : "");
    Array.prototype.forEach.call(props.querySelectorAll("[data-only]"), function (el) {
      var want = el.getAttribute("data-only");
      el.hidden = want !== kind && want !== also && want !== extra;
    });
    // Con viñetas el texto va a la izquierda: la alineación no haría nada.
    var alignField = props.querySelector("[data-align-field]");
    if (alignField && kind === "text") alignField.hidden = !!one.list;
    if (kind === "text") showFormat();
    // Sin viñetas el campo dice «Sin viñetas»: la clave no se guarda.
    var bullet = props.querySelector('[data-prop="list"]');
    if (bullet && kind === "text" && bullet !== document.activeElement) {
      bullet.value = one.list === true ? "dot" : (one.list || "");
    }
    var row = props.querySelector('[data-props-for~="' + kind + '"]');
    Array.prototype.forEach.call(row.querySelectorAll("[data-prop]"), function (input) {
      var name = input.getAttribute("data-prop");
      // Una casilla sin su clave está apagada: las viñetas solo se escriben
      // cuando están puestas, y sin esto quedaba marcada la del texto anterior.
      var DEFAULTS = { border: 0, border_color: "#18181B", mask: "", radius: 0 };
      if (!(name in one) && input.type !== "checkbox") {
        if (name in DEFAULTS && input !== document.activeElement) input.value = DEFAULTS[name];
        return;
      }
      if (input === document.activeElement) return;
      if (input.type === "checkbox") input.checked = !!one[name];
      else input.value = String(one[name]);
    });
  }

  /* **Las cajas de texto tienen el tamaño que se les pone** (octubre de 2026).
     Antes una caja crecía sola al escribir, al soltar un tirador y al cambiar
     la letra, y el correo salía más largo que el lienzo. Ahora lo que no cabe
     queda oculto, igual que en el correo, y se avisa; «Ajustar la caja al
     texto» la agranda cuando uno quiere. Una caja con variables (`*|NOMBRE|*`)
     es la excepción: en el correo crece con el largo de cada valor, que aquí no
     se sabe. */
  var MARKS = /\*\|[#^/]?[A-Z0-9_]+\|\*/;

  function hasMarks(one) { return MARKS.test(one.text || ""); }

  /* Lo que mide lo escrito en esa caja, con su ancho. */
  function needed(one) {
    var probe = document.createElement("div");
    probe.className = "cv-item cv-item--text cv-probe";
    if (one.list) fillText(probe, one); else probe.textContent = one.text || " ";
    paintItem(probe, one);
    probe.style.height = "auto";
    // Fuera de la hoja, que lleva el zoom: se mide a su tamaño de verdad.
    root.appendChild(probe);
    var need = Math.ceil(probe.scrollHeight);
    root.removeChild(probe);
    return need;
  }

  /* Agrandar la caja hasta que quepa (el botón): hasta el borde de la hoja,
     cuyo alto solo mueve quien la arrastra o escribe su número. */
  function fitText(i) {
    var one = doc.items[i];
    if (!one || one.t !== "text") return;
    var need = needed(one);
    if (need > one.h) one.h = Math.min(need, doc.h - one.y);
  }

  /* Qué cajas no caben: se marcan y se avisa. Se mira al abrir, al terminar de
     escribir, al soltar un tirador y al cambiar la letra, no a cada dibujo. */
  var cut = {};
  function checkFit() {
    cut = {};
    doc.items.forEach(function (one, i) {
      if (one.t === "text" && needed(one) > one.h + 1) cut[i] = hasMarks(one) ? "grow" : "cut";
    });
  }

  /* ------------------------------------------------------------ agregar */

  /* Lo que se inserta entra arriba de la hoja, que es donde se está mirando, y
     de ahí se mueve a mano. Antes buscaba un hueco libre y, si no lo había, no
     insertaba nada: una figura pide 160 px y una foto puede pedir 400, así que
     con la hoja medio llena los botones de Geometría e Imagen parecían muertos.
     Ahora **siempre entra algo**, y la hoja no cambia de alto por ello. */
  var dropped = 0;          // cuántas van seguidas, para no apilarlas encima

  function place(one, at) {
    if (doc.items.length >= L.maxItems) { say(S.maxItems); return; }
    // Lo que no quepa se achica al entrar: crear algo que después no se puede
    // guardar por salirse de la hoja no le sirve a nadie.
    var room = Math.max(16, doc.h - 2 * GAP);
    if (one.h > room) {
      if (one.t === "image" && one.r) one.w = Math.max(16, Math.round(room * one.r));
      one.h = room;
    }
    if (one.w > W) one.w = W;
    // Soltada sobre la hoja, o pulsada en Subidas: entra donde se soltó, o en
    // medio de lo que se ve (octubre de 2026).
    if (at) {
      one.x = clamp(Math.round(at.x - one.w / 2), 0, W - one.w);
      one.y = clamp(Math.round(at.y - one.h / 2), 0, Math.max(0, doc.h - one.h));
      doc.items.push(one);
      pick(doc.items.length - 1);
      render(); commit();
      return;
    }
    // En cascada, como en un editor de diapositivas: la siguiente entra un
    // poco más abajo y a la derecha, y se vuelve arriba al llegar al borde de
    // abajo. Lo ancho no cuenta para eso: una figura ocupa la hoja entera y
    // reiniciaría la cascada en cada inserción.
    var step = dropped * GAP;
    if (GAP + step + one.h > doc.h) { dropped = 0; step = 0; }
    dropped += 1;
    one.x = clamp(one.x + step, 0, W - one.w);
    one.y = clamp(GAP + step, 0, doc.h - one.h);
    doc.items.push(one);
    pick(doc.items.length - 1);
    render(); commit();
    var el = stage.querySelector('.cv-item[data-item="' + sel + '"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }

  /* Cómo entra cada figura del menú de Geometría: el rectángulo a lo ancho,
     como siempre; la línea fina y gris, centrada; las demás, cuadradas. */
  var SHAPE_START = {
    rect: { x: 0, w: W, h: 160 },
    line: { x: Math.round((W - 400) / 2), w: 400, h: 2, bg: "#CBD5E1" },
    ellipse: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    triangle: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    star: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    arrow: { x: Math.round((W - 200) / 2), w: 200, h: 120 },
    diamond: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    pentagon: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    hexagon: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    octagon: { x: Math.round((W - 160) / 2), w: 160, h: 160 },
    heart: { x: Math.round((W - 160) / 2), w: 160, h: 150 },
    cross: { x: Math.round((W - 140) / 2), w: 140, h: 140 },
    bubble: { x: Math.round((W - 220) / 2), w: 220, h: 160 },
    double_arrow: { x: Math.round((W - 240) / 2), w: 240, h: 110 },
  };

  /* Los textos de partida del panel Texto (octubre de 2026), como en Canva:
     un título, un subtítulo, un texto y una lista. */
  var PRESETS = {
    title: { size: 36, bold: true, text: "newTitle" },
    subtitle: { size: 24, bold: true, text: "newSubtitle" },
    body: { size: 16, bold: false, text: "newText" },
    list: { size: 16, bold: false, text: "newList", list: true },
  };

  function add(kind, figure, preset) {
    say("");
    if (doc.items.length >= L.maxItems) { say(S.maxItems); return; }
    if (kind === "image") { pickImage(null); return; }
    if (kind === "logo") { useLogo(); return; }
    if (kind === "text") {
      var p = PRESETS[preset] || PRESETS.body;
      var text = S[p.text] || S.newText;
      var one = { t: "text", x: 40, w: W - 80, h: 34, text: text, font: "Arial",
                  size: p.size, color: "#18181B", bold: p.bold, italic: false,
                  align: "left", line: 1.4 };
      if (p.list) one.list = "dot";
      one.h = Math.max(16, needed(one));
      place(one);
    } else if (kind === "button") {
      // Sin `https://` escrito dentro: el campo lo enseña como marca de agua.
      // Escrito, quien pegaba una dirección acababa con «https://https://…».
      place({ t: "button", x: (W - 200) / 2, w: 200, h: 48, text: S.newButton,
              href: "", font: "Arial", size: 16, color: "#FFFFFF", bg: "#31A9E8",
              bold: true, italic: false, align: "center", radius: 8 });
    } else if (kind === "shape") {
      var shape = SHAPE_START[figure] ? figure : "rect";
      var start = SHAPE_START[shape];
      place({ t: "shape", x: start.x, w: start.w, h: start.h, bg: start.bg || "#E0F2FE",
              radius: 0, shape: shape, rot: 0 });
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
    var files = Array.prototype.slice.call(fileInput.files || []);
    // Para cambiar una se usa la primera; para agregar, hasta cinco de una vez.
    if (replacing !== null && replacing !== undefined) {
      if (files[0]) sendImage(files[0], replacing);
      return;
    }
    files.slice(0, 5).forEach(function (file) { sendImage(file, null, visibleCenter()); });
  });

  /* El punto de la hoja que está en medio de lo que se ve: ahí entra lo que se
     pulsa en Subidas o se pega. */
  function visibleCenter() {
    var sheet = stage.querySelector(".cv-sheet");
    if (!sheet || !scroller) return null;
    var box = sheet.getBoundingClientRect(), view = scroller.getBoundingClientRect();
    var x = unzoom((view.left + view.right) / 2 - box.left);
    var y = unzoom((Math.max(view.top, box.top) + Math.min(view.bottom, box.bottom)) / 2 - box.top);
    return { x: clamp(x, 0, W), y: clamp(y, 0, doc.h) };
  }

  /* Un SVG no se sube tal cual (octubre de 2026): puede llevar código. Se
     dibuja en el navegador y sube su PNG, de hasta 1,200 px de ancho. */
  function isSvg(file) {
    return file && (file.type === "image/svg+xml" || /\.svg$/i.test(file.name || ""));
  }

  function svgToPng(file, done) {
    var url = URL.createObjectURL(file);
    var img = new Image();
    img.onload = function () {
      var w = img.naturalWidth || 1200, h = img.naturalHeight || 1200;
      var scale = Math.min(1, 1200 / w) || 1;
      if (w < 600) scale = 600 / w;
      var c = document.createElement("canvas");
      c.width = Math.round(w * scale);
      c.height = Math.round(h * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob(function (blob) {
        if (!blob) { say(S.svgFailed); return; }
        done(new File([blob], (file.name || "imagen").replace(/\.svg$/i, "") + ".png",
                      { type: "image/png" }));
      }, "image/png");
    };
    img.onerror = function () { URL.revokeObjectURL(url); say(S.svgFailed); };
    img.src = url;
  }

  /* Sube una foto y la pone en la hoja. `replace` cambia la del elemento que
     diga, y con null entra una nueva. La misma ruta para el botón y para lo
     que se pega: el servidor la revisa por lo que trae dentro y la achica. */
  function sendImage(file, replace, at) {
    if (isSvg(file)) {
      svgToPng(file, function (png) { sendImage(png, replace, at); });
      return;
    }
    var body = new FormData();
    body.append("archivo", file);
    askImage(root.getAttribute("data-upload"), body, replace, at);
  }

  /* El logo de la empresa (octubre de 2026): el servidor pone una copia como
     foto de esta cuenta y contesta lo mismo que al subir una. */
  function useLogo() {
    askImage(root.getAttribute("data-logo"), new FormData(), null);
  }

  function askImage(url, body, replace, at) {
    say(S.uploading);
    body.append("csrf_token", saveForm.querySelector("[name=csrf_token]").value);
    fetch(url, { method: "POST", body: body, credentials: "same-origin" })
      .then(function (r) { return r.json().catch(function () { return { error: S.uploadFailed }; }); })
      .then(function (answer) {
        if (answer.error || !answer.name) { say(answer.error || S.uploadFailed); return; }
        say("");
        var r = answer.width / Math.max(answer.height, 1);
        if (replace !== null && replace !== undefined && doc.items[replace]) {
          var one = doc.items[replace];
          one.name = answer.name;
          one.r = Math.round(r * 10000) / 10000;
          // La caja toma la proporción de la foto nueva, con el mismo ancho.
          one.h = Math.max(16, Math.round(one.w / r));
          delete one.fit;
          render(); commit();
          return;
        }
        // Entra a la mitad del ancho, con su proporción: se puede mover y
        // cabe otra al lado. «Ancho completo» la estira.
        putImage(answer.name, r, at);
        uploaded(answer);
      })
      .catch(function () { say(S.uploadFailed); });
  }

  function putImage(name, r, at) {
    var w = W / 2;
    var h = Math.max(16, Math.min(Math.round(w / r), L.maxHeight));
    place({ t: "image", x: Math.round((W - w) / 2), w: w, h: h, name: name,
            r: Math.round(r * 10000) / 10000, href: "", alt: "" }, at);
  }

  /* ---------------------------------------------------------- Subidas */

  /* Las fotos que ya subió la cuenta (octubre de 2026), de la más nueva a la
     más vieja: se pulsan para ponerlas en medio de lo que se ve, o se
     arrastran a donde se quieran. Se piden la primera vez que se abre el
     panel. */
  var gallery = document.querySelector("[data-uploads]");
  var galleryMore = document.querySelector("[data-uploads-more]");
  var galleryEmpty = document.querySelector("[data-uploads-empty]");
  var galleryNext = null, galleryAsked = false;

  function tile(one, first) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "uploads__one";
    b.draggable = true;
    b.setAttribute("data-photo", one.name);
    b.setAttribute("data-ratio", one.width && one.height ? one.width / one.height : 0);
    var img = document.createElement("img");
    img.src = one.url;
    img.alt = "";
    img.loading = "lazy";
    b.appendChild(img);
    if (first && gallery.firstChild) gallery.insertBefore(b, gallery.firstChild);
    else gallery.appendChild(b);
  }

  function loadGallery(more) {
    if (!gallery) return;
    galleryAsked = true;
    var url = gallery.getAttribute("data-list") + (more && galleryNext ? "?antes=" + encodeURIComponent(galleryNext) : "");
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (answer) {
        (answer.images || []).forEach(function (one) { tile(one, false); });
        galleryNext = answer.antes || null;
        galleryMore.hidden = !answer.more;
        galleryEmpty.hidden = !!gallery.children.length;
      })
      .catch(function () { /* sin la lista, se sube igual */ });
  }

  function uploaded(answer) {
    if (!gallery || !galleryAsked) return;
    tile(answer, true);
    galleryEmpty.hidden = true;
  }

  /* La proporción de una foto de la lista: la guardada, o la de la imagen. */
  function ratioOf(b, done) {
    var r = parseFloat(b.getAttribute("data-ratio"));
    if (r > 0) { done(r); return; }
    var img = b.querySelector("img");
    if (img.complete && img.naturalWidth) { done(img.naturalWidth / img.naturalHeight); return; }
    img.addEventListener("load", function () { done(img.naturalWidth / img.naturalHeight); });
  }

  if (gallery) {
    if (rail) {
      rail.addEventListener("click", function (e) {
        var b = e.target.closest('[data-panel="uploads"]');
        if (b && !galleryAsked) loadGallery(false);
      });
      if (rail.querySelector('[data-panel="uploads"].is-on')) loadGallery(false);
    } else loadGallery(false);
    galleryMore.addEventListener("click", function () { loadGallery(true); });
    gallery.addEventListener("click", function (e) {
      var b = e.target.closest("[data-photo]");
      if (!b) return;
      ratioOf(b, function (r) { putImage(b.getAttribute("data-photo"), r, visibleCenter()); });
    });
    gallery.addEventListener("dragstart", function (e) {
      var b = e.target.closest("[data-photo]");
      if (!b) return;
      e.dataTransfer.setData("application/x-sobreala-photo", JSON.stringify({
        name: b.getAttribute("data-photo"), ratio: parseFloat(b.getAttribute("data-ratio")) || 0 }));
      e.dataTransfer.effectAllowed = "copy";
    });
  }

  /* Soltar sobre la hoja: una foto de Subidas o archivos del escritorio entran
     donde se sueltan, con el zoom descontado. */
  function dropPoint(e) {
    var sheet = stage.querySelector(".cv-sheet");
    if (!sheet) return null;
    var box = sheet.getBoundingClientRect();
    return { x: clamp(unzoom(e.clientX - box.left), 0, W),
             y: clamp(unzoom(e.clientY - box.top), 0, doc.h) };
  }

  if (scroller) {
    scroller.addEventListener("dragover", function (e) {
      var types = Array.prototype.slice.call(e.dataTransfer.types || []);
      if (types.indexOf("Files") < 0 && types.indexOf("application/x-sobreala-photo") < 0) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      scroller.classList.add("is-drop");
    });
    scroller.addEventListener("dragleave", function (e) {
      if (!scroller.contains(e.relatedTarget)) scroller.classList.remove("is-drop");
    });
    scroller.addEventListener("drop", function (e) {
      scroller.classList.remove("is-drop");
      var at = dropPoint(e);
      var mine = e.dataTransfer.getData("application/x-sobreala-photo");
      if (mine) {
        e.preventDefault();
        var data = JSON.parse(mine);
        if (data.ratio > 0) { putImage(data.name, data.ratio, at); return; }
        var b = gallery && gallery.querySelector('[data-photo="' + CSS.escape(data.name) + '"]');
        if (b) ratioOf(b, function (r) { putImage(data.name, r, at); });
        return;
      }
      var files = Array.prototype.filter.call(e.dataTransfer.files || [], function (f) {
        return f.type.indexOf("image/") === 0 || isSvg(f);
      });
      if (!files.length) return;
      e.preventDefault();
      files.slice(0, 5).forEach(function (file) { sendImage(file, null, at); });
    });
  }

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
    // Mientras se escribe, pulsar fuera del texto termina de escribir: el
    // foco puede estar en la barra (dando formato), y no en el texto.
    if (editing && !editing.contains(e.target)) { endEditing(); return; }

    // Mientras se recorta, el ratón es del recuadro: mover dentro, estirar por
    // las esquinas, y un clic fuera termina.
    if (cropping !== null) {
      var handle = e.target.closest("[data-crop-handle]");
      var frame = e.target.closest("[data-crop-frame]");
      if (handle || frame) {
        var box = frame || e.target.closest("[data-crop]").querySelector("[data-crop-frame]");
        drag = { mode: "crop-" + (handle ? handle.getAttribute("data-crop-handle") : "move"),
                 x0: e.clientX, y0: e.clientY, frame: box, moved: false,
                 start: { x: parseFloat(box.style.left), y: parseFloat(box.style.top),
                          w: parseFloat(box.style.width), h: parseFloat(box.style.height) } };
        e.preventDefault();
        return;
      }
      if (!e.target.closest("[data-crop]")) { stopCrop(); return; }
      e.preventDefault();
      return;
    }
    // La capa de los tiradores también trae su `data-item`: lo de ella es de
    // lo elegido, así que de ahí en adelante da igual por dónde se agarró.
    var el = e.target.closest(".cv-item, .cv-chrome");
    if (!el) {
      // Arrastrar sobre la hoja vacía encierra lo que toque el recuadro.
      if (editing) editing.blur();
      var edge = sheet.getBoundingClientRect();
      // Con Ctrl o Mayús, lo encerrado se suma a lo elegido (octubre de 2026).
      var adding = e.shiftKey || e.ctrlKey || e.metaKey;
      drag = { mode: "marquee", sheet: sheet, moved: false,
               ax: unzoom(e.clientX - edge.left), ay: unzoom(e.clientY - edge.top),
               add: adding, was: picked.slice() };
      if (!adding) { pick(null); render(); }
      e.preventDefault();
      return;
    }
    if (el.isContentEditable) return;
    var i = +el.getAttribute("data-item");
    var turn = e.target.closest("[data-turn]");
    if (turn) {
      var box = doc.items[i];
      var seat = el.getBoundingClientRect();
      drag = { mode: "turn", i: i, moved: false,
               cx: seat.left + seat.width / 2, cy: seat.top + seat.height / 2,
               start: clone(box) };
      e.preventDefault();
      return;
    }
    var handle = e.target.closest("[data-handle]");
    if ((e.shiftKey || e.ctrlKey || e.metaKey) && !handle) {
      // Ctrl o Mayús suman y quitan (Cmd en Mac), y arrastran al grupo entero
      // con él.
      var group = tied(i), out = picked.slice();
      if (isPicked(i)) {
        out = out.filter(function (k) { return group.indexOf(k) < 0; });
      } else {
        out = out.concat(group);
      }
      pick(out);
      render();
      return;
    }
    // Pulsar algo que ya estaba elegido no deshace la selección: es como se
    // arrastran varios de una vez.
    if (!isPicked(i)) { pick(tied(i)); render(); }
    // Sin captura del puntero: con ella el doble clic le llegaría a la hoja
    // entera y no al texto. El movimiento se escucha en la ventana.
    // Mover se llama «drag» y no «move»: el tamaño se decide mirando si el
    // modo trae n, s, e u o, y «move» trae una e.
    drag = { mode: handle ? handle.getAttribute("data-handle") : "drag", i: i,
             x0: e.clientX, y0: e.clientY, start: clone(doc.items[i]), moved: false,
             many: picked.slice(), starts: chosen().map(clone) };
    e.preventDefault();
  });

  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var sheet = stage.querySelector(".cv-sheet");
    if (drag.mode === "grip") {
      doc.h = clamp(Math.round(drag.h0 + unzoom(e.clientY - drag.y0)), drag.min, L.maxHeight);
      if (sheet) sheet.style.height = doc.h + "px";
      sizeZoom();
      drag.moved = true;
      return;
    }
    if (drag.mode === "turn") {
      var turning = doc.items[drag.i];
      if (!turning) return;
      drag.moved = true;
      // Cero es hacia arriba, y hacia la derecha como en CSS.
      var angle = Math.atan2(e.clientY - drag.cy, e.clientX - drag.cx);
      var degrees = Math.round(angle * 180 / Math.PI) + 90;
      if (e.shiftKey) degrees = Math.round(degrees / 15) * 15;
      turning.rot = ((degrees % 360) + 360) % 360;
      fitRot(turning);
      repaint(sheet, turning, drag.i);
      return;
    }
    if (drag.mode.indexOf("crop-") === 0) {
      var cropped = doc.items[cropping];
      if (!cropped) return;
      var a = drag.start;
      var cdx = Math.round(unzoom(e.clientX - drag.x0)), cdy = Math.round(unzoom(e.clientY - drag.y0));
      drag.moved = true;
      var ratio = cropped.w / Math.max(cropped.h, 1);
      var want;
      if (drag.mode === "crop-move") {
        want = { x: a.x + cdx, y: a.y + cdy, w: a.w };
      } else {
        // La esquina de enfrente se queda donde está: lo que crece es hacia
        // donde se tira.
        var wide = drag.mode.indexOf("e") >= 0 ? a.w + cdx : a.w - cdx;
        var tall = wide / ratio;
        want = { w: wide,
                 x: drag.mode.indexOf("w") >= 0 ? a.x + a.w - wide : a.x,
                 y: drag.mode.indexOf("n") >= 0 ? a.y + a.h - tall : a.y };
      }
      cropped.crop = cropFrom(cropped, want);
      var seat = photoBox(cropped);
      drag.frame.style.left = (cropped.crop[0] * seat.w) + "px";
      drag.frame.style.top = (cropped.crop[1] * seat.h) + "px";
      drag.frame.style.width = (cropped.crop[2] * seat.w) + "px";
      drag.frame.style.height = (cropped.crop[3] * seat.h) + "px";
      return;
    }
    if (drag.mode === "marquee") {
      var edge = drag.sheet.getBoundingClientRect();
      drag.bx = clamp(unzoom(e.clientX - edge.left), 0, W);
      drag.by = Math.max(0, unzoom(e.clientY - edge.top));
      drag.moved = true;
      var mark = drag.sheet.querySelector(".cv-marquee");
      if (!mark) {
        mark = document.createElement("div");
        mark.className = "cv-marquee";
        drag.sheet.appendChild(mark);
      }
      mark.style.left = Math.min(drag.ax, drag.bx) + "px";
      mark.style.top = Math.min(drag.ay, drag.by) + "px";
      mark.style.width = Math.abs(drag.bx - drag.ax) + "px";
      mark.style.height = Math.abs(drag.by - drag.ay) + "px";
      return;
    }
    var one = doc.items[drag.i], a = drag.start;
    var dx = Math.round(unzoom(e.clientX - drag.x0)), dy = Math.round(unzoom(e.clientY - drag.y0));
    if (!dx && !dy && !drag.moved) return;
    drag.moved = true;

    // Varios a la vez: todos se mueven lo mismo, y lo que manda es la caja que
    // los abarca, que es la que no puede salirse de la hoja.
    if (drag.mode === "drag" && drag.many.length > 1) {
      var box = around(drag.starts);
      var mx = clamp(dx, -box.x, W - (box.x + box.w));
      var my = clamp(dy, -box.y, doc.h - (box.y + box.h));
      drag.many.forEach(function (k, at) {
        doc.items[k].x = drag.starts[at].x + mx;
        doc.items[k].y = drag.starts[at].y + my;
        repaint(sheet, doc.items[k], k);
      });

      if (sheet) guides(sheet, []);
      return;
    }
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
    // Nada baja de 16 px, salvo el grosor de una línea, que es su alto.
    w = Math.max(16, w); h = isLine(one) ? a.h : Math.max(16, h);
    var fit = mode === "drag" ? snap(drag.i, x, y, w, h) : { x: x, y: y, lines: [] };
    one.x = clamp(Math.round(fit.x), 0, W - Math.min(w, W));
    one.y = clamp(Math.round(fit.y), 0, doc.h - Math.min(h, doc.h));
    var wide = Math.min(w, W - one.x), tall = Math.min(h, doc.h - one.y);
    // Al topar con el borde de la hoja, una foto tirada de una esquina se
    // quedaba con el ancho recortado y el alto entero: cambiaba de proporción
    // y se veía estirada. Si el ancho se recorta, el alto lo sigue.
    if (one.t === "image" && mode.length === 2 && wide !== w) {
      tall = Math.max(16, Math.round(wide * h / w));
    }
    one.w = wide;
    one.h = tall;
    if (one.t === "image" && one.fit) delete one.fit;

    var el = repaint(sheet, one, drag.i);
    if (el) {
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
    if (was.mode === "turn") {
      if (was.moved) { render(); commit(); }
      return;
    }
    if (was.mode.indexOf("crop-") === 0) {
      if (was.moved) { render(); commitSoon(); }
      return;
    }
    if (was.mode === "marquee") {
      var mark = was.sheet.querySelector(".cv-marquee");
      if (mark) mark.remove();
      if (!was.moved) { pick(was.add ? was.was : null); render(); return; }
      var area = { x: Math.min(was.ax, was.bx), y: Math.min(was.ay, was.by),
                   w: Math.abs(was.bx - was.ax), h: Math.abs(was.by - was.ay) };
      var found = was.add ? was.was.slice() : [];
      doc.items.forEach(function (one, i) {
        if (!touch(area, one)) return;
        // Lo que está agrupado entra entero, como al pulsarlo.
        tied(i).forEach(function (k) { if (found.indexOf(k) < 0) found.push(k); });
      });
      pick(found);
      render();
      return;
    }
    if (was.moved) {
      if (was.mode !== "grip" && was.mode !== "drag") checkFit();
      chosen().forEach(fitRot);
      render(); commit();
    }
  }
  window.addEventListener("pointerup", endDrag);
  window.addEventListener("pointercancel", endDrag);

  /* --------------------------------------------------------- escribir texto */

  stage.addEventListener("dblclick", function (e) {
    var el = e.target.closest(".cv-item--text");
    if (!el) return;
    pick(+el.getAttribute("data-item"));
    Array.prototype.forEach.call(el.querySelectorAll(".cv-handle"), function (h) { h.remove(); });
    // Con viñetas se escribe en plano, con la misma sangría: los renglones se
    // parten igual, y las viñetas vuelven al terminar.
    var writing = doc.items[+el.getAttribute("data-item")];
    if (writing && writing.list) { el.textContent = ""; fillRuns(el, runsOf(writing)); }
    try { el.contentEditable = "plaintext-only"; } catch (err) { el.contentEditable = "true"; }
    if (el.contentEditable !== "plaintext-only") el.contentEditable = "true";
    el.classList.add("is-editing");
    editing = el;
    // La barra del texto, para darle formato mientras se escribe.
    showProps();
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
    // Lo escrito, con su formato por palabras.
    syncEditing();
    // La caja no crece (octubre de 2026): lo que no cabe se ve desplazando
    // dentro mientras se escribe, y se avisa, porque en el correo no sale.
    var over = needed(one) > one.h + 1;
    warn.textContent = over ? (hasMarks(one) ? S.textGrows : S.textCut) : "";
    warn.hidden = !over;
  });

  stage.addEventListener("focusout", function (e) {
    if (!editing || e.target !== editing) return;
    // A la barra de lo elegido no se sale: es para darle formato a lo
    // seleccionado (octubre de 2026).
    if (e.relatedTarget && props.contains(e.relatedTarget)) return;
    endEditing();
  });
  // Y de la barra a cualquier otro sitio que no sea el texto, sí.
  props.addEventListener("focusout", function (e) {
    if (!editing) return;
    var to = e.relatedTarget;
    if (to && (props.contains(to) || to === editing)) return;
    setTimeout(function () {
      var now = document.activeElement;
      if (editing && !(now && (props.contains(now) || now === editing))) endEditing();
    }, 0);
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

  /* Al salir del campo del enlace, lo que se escribió sin esquema lo lleva:
     «coop.com/asamblea» queda como «https://coop.com/asamblea». */
  props.addEventListener("focusout", function (e) {
    var field = e.target.closest && e.target.closest("[data-href]");
    var one = item();
    if (!field || !one) return;
    var value = field.value.trim();
    if (!value || /^(https:\/\/|mailto:)/i.test(value)) return;
    field.value = "https://" + value.replace(/^(http:\/\/|\/+)/i, "");
    one.href = field.value;
    render(); commit();
  });

  props.addEventListener("input", function (e) {
    // Negrita, cursiva, subrayado y color de un texto: a lo seleccionado
    // mientras se escribe, o, el subrayado, al texto entero.
    var fmt = e.target.closest('[data-prop="bold"], [data-prop="italic"], [data-prop="color"], [data-format="u"]');
    var cur = item();
    if (fmt && cur && cur.t === "text") {
      var key = { bold: "b", italic: "i", color: "color" }[fmt.getAttribute("data-prop")] || "u";
      var val = fmt.type === "checkbox" ? fmt.checked : String(fmt.value).toUpperCase();
      if (key === "u" || (editing && formatSpan(cur).part)) {
        applyFormat(key, val, key !== "color");
        return;
      }
    }
    if (e.target.closest("[data-link-url]")) return;
    var page = e.target.closest("[data-page-bg]");
    if (page) {
      doc.bg = page.value.toUpperCase();
      var sheet = stage.querySelector(".cv-sheet");
      if (sheet) sheet.style.backgroundColor = doc.bg;
      commitSoon();
      return;
    }
    // El alto de la hoja se escribe, y también se arrastra por el tirador de
    // abajo. Nunca por debajo de lo que ya hay dentro: eso lo dejaría fuera.
    var high = e.target.closest("[data-sheet-h]");
    if (high) {
      var want = parseInt(high.value, 10);
      if (isNaN(want)) return;
      var least = Math.max(L.minHeight, lowest());
      doc.h = clamp(want, least, L.maxHeight);
      say(doc.h !== want ? S.sheetLeast.replace("{px}", doc.h) : "");
      var box = stage.querySelector(".cv-sheet");
      if (box) box.style.height = doc.h + "px";
      commitSoon();
      return;
    }
    var input = e.target.closest("[data-prop]");
    var one = item();
    if (!input || !one) return;
    var name = input.getAttribute("data-prop");
    var value = input.type === "checkbox" ? input.checked : input.value;
    if (name === "size" || name === "radius" || name === "rot" || name === "h" || name === "border") {
      value = parseInt(value, 10);
      if (isNaN(value)) return;
      if (name === "size") value = clamp(value, L.minSize, L.maxSize);
      if (name === "rot") value = ((value % 360) + 360) % 360;
      if (name === "border") value = clamp(value, 0, 20);
    }
    // Sin forma, sin borde: la clave no se guarda (octubre de 2026).
    if ((name === "mask" && !value) || (name === "border" && !value)) {
      delete one[name];
      repaint(stage, one, sel);
      commitSoon();
      return;
    }
    if (name === "border" && !one.border_color) one.border_color = "#18181B";
    if (name === "h") {
      // El grosor de una línea, que crece y adelgaza desde su centro.
      if (!isLine(one)) return;
      value = clamp(value, L.lineMin, L.lineMax);
      one.y = clamp(Math.round(one.y + (one.h - value) / 2), 0, Math.max(0, doc.h - value));
    }
    if (name === "shape" && value !== one.shape) {
      // A línea queda fina, y de línea a otra figura recupera cuerpo; las dos
      // desde el centro de donde estaba.
      var mid = one.y + one.h / 2;
      if (value === "line") one.h = 2;
      else if (one.shape === "line") one.h = 120;
      one.y = clamp(Math.round(mid - one.h / 2), 0, Math.max(0, doc.h - one.h));
    }
    if (name === "line") value = parseFloat(value);
    if (name === "bg" || name === "color" || name === "border_color") value = String(value).toUpperCase();
    one[name] = value;
    // Lo de la caja entera borra lo de cada tramo: «negrita» es todo el texto.
    var runKey = { bold: "b", italic: "i", color: "color" }[name];
    if (runKey && one.runs) {
      one.runs.forEach(function (r) { delete r[runKey]; });
      tidyRuns(one, one.runs);
      if (editing) refillEditing(one, formatSpan(one), false);
    }
    // Las viñetas solo se escriben puestas, como las guarda el servidor.
    if (name === "list" && !value) delete one.list;
    if (name === "rot" || name === "h" || name === "shape") fitRot(one);
    if (one.t === "text") checkFit();
    var el = repaint(stage, one, sel);
    if (el && name === "text") el.firstChild ? (el.firstChild.nodeValue = value) : (el.textContent = value);
    // El enlace de una foto cambia lo que se puede encimar: se repinta.
    if (name === "href" && one.t === "image") render();
    commitSoon();
  });

  props.addEventListener("change", function () { render(); });

  /* --------------------------------------------- lo que vale para varios */

  /* Borrar de atrás hacia delante: si no, cada corte le cambiaría el índice a
     los siguientes. */
  function dropPicked() {
    picked.slice().sort(function (a, b) { return b - a; })
      .forEach(function (i) { doc.items.splice(i, 1); });
    pick(null);
  }

  /* Duplicar lo elegido, un poco más abajo y a la derecha, y dejar la copia
     elegida. Un grupo copiado sigue siendo un grupo, pero uno nuevo. */
  function duplicate(list) {
    var copies = list.map(clone), tie = {};
    if (copies.length + doc.items.length > L.maxItems) { say(S.maxItems); return; }
    say("");
    var out = [];
    copies.forEach(function (one) {
      one.x = clamp(one.x + 12, 0, W - one.w);
      one.y = clamp(one.y + 12, 0, L.maxHeight - one.h);
      if (one.g) {
        if (!tie[one.g]) tie[one.g] = freeTie();
        one.g = tie[one.g];
      }
      doc.items.push(one);
      out.push(doc.items.length - 1);
    });
    pick(out);
    render(); commit();
  }

  /* Un número de grupo que no esté usado. */
  function freeTie() {
    var top = 0;
    doc.items.forEach(function (one) { if (one.g > top) top = one.g; });
    return Math.min(top + 1, 999);
  }

  function alignPicked(what) {
    var list = chosen();
    if (list.length < 2) return;
    var box = around(list);
    list.forEach(function (one) {
      if (what === "align-l") one.x = box.x;
      else if (what === "align-r") one.x = box.x + box.w - one.w;
      else if (what === "align-cx") one.x = Math.round(box.x + (box.w - one.w) / 2);
      else if (what === "align-t") one.y = box.y;
      else if (what === "align-b") one.y = box.y + box.h - one.h;
      else if (what === "align-cy") one.y = Math.round(box.y + (box.h - one.h) / 2);
      one.x = clamp(one.x, 0, W - one.w);
      one.y = clamp(one.y, 0, L.maxHeight - one.h);
    });
  }

  /* Repartir: el primero y el último se quedan donde están y los del medio se
     acomodan con el mismo aire entre ellos. */
  function spreadPicked(axis) {
    var list = chosen();
    if (list.length < 3) return;
    var pos = axis === "x" ? "x" : "y", size = axis === "x" ? "w" : "h";
    var order = list.slice().sort(function (a, b) { return a[pos] - b[pos]; });
    var first = order[0], last = order[order.length - 1];
    var used = order.reduce(function (sum, one) { return sum + one[size]; }, 0);
    var gap = ((last[pos] + last[size]) - first[pos] - used) / (order.length - 1);
    var at = first[pos] + first[size] + gap;
    order.slice(1, -1).forEach(function (one) {
      one[pos] = Math.round(at);
      at += one[size] + gap;
    });
  }

  props.addEventListener("click", function (e) {
    var b = e.target.closest("[data-action]");
    if (!b) return;
    var what = b.getAttribute("data-action");
    if (picked.length > 1) {
      if (what === "delete") dropPicked();
      else if (what === "duplicate") { duplicate(chosen()); return; }
      else if (what === "group") {
        var tie = freeTie();
        chosen().forEach(function (one) { one.g = tie; });
      } else if (what === "ungroup") {
        chosen().forEach(function (one) { delete one.g; });
      } else if (what.indexOf("align-") === 0) alignPicked(what);
      else if (what === "spread-x") spreadPicked("x");
      else if (what === "spread-y") spreadPicked("y");
      else return;
      render(); commit();
      return;
    }
    // Pegar la hoja a lo que hay dentro. Va antes de pedir un elegido porque
    // es de la barra de cuando no hay ninguno, y es lo que quita el blanco que
    // se veía en el correo entre lo último y el botón de la baja.
    if (what === "fit") {
      doc.h = clamp(lowest(), L.minHeight, L.maxHeight);
      render(); commit();
      return;
    }
    var one = item();
    if (!one) return;
    var list = doc.items;
    if (what === "fit-text") {
      fitText(sel);
      checkFit();
      render(); commit();
      return;
    }
    if (what === "delete") {
      list.splice(sel, 1);
      pick(null);
    } else if (what === "duplicate") {
      duplicate([one]);
      return;
    } else if (what === "ungroup") {
      delete one.g;
    } else if (what === "straight") {
      one.rot = 0;
    } else if (what === "crop") {
      cropping = cropping === sel ? null : sel;
      say(cropping === null ? "" : S.cropHow);
      render();
      return;
    } else if (what === "uncrop") {
      delete one.crop;
      cropping = null;
    } else if (what === "replace") {
      pickImage(sel);
      return;
    } else if (what === "full") {
      // Todo el ancho, con la proporción de la foto (o la de su caja, en las
      // que se guardaron antes de que se anotara).
      var r = one.r || (one.w / Math.max(one.h, 1));
      one.x = 0; one.w = W;
      if (one.t === "image") { one.h = Math.max(16, Math.round(W / r)); delete one.fit; }
      one.y = Math.min(one.y, Math.max(0, doc.h - one.h));
    } else if (what === "front" || what === "back") {
      // Solo entre fotos y rectángulos: los textos y botones siempre van
      // delante.
      var backs = [];
      list.forEach(function (x, k) { if (BACK[x.t]) backs.push(k); });
      var at = backs.indexOf(sel);
      var to = what === "front" ? backs[at + 1] : backs[at - 1];
      if (to === undefined) return;
      var tmp = list[to]; list[to] = list[sel]; list[sel] = tmp;
      pick(to);
    }
    render(); commit();
  });

  /* ---------------------------------------------------------------- teclas */

  document.addEventListener("keydown", function (e) {
    var typing = e.target.closest && e.target.closest("input, select, textarea, [contenteditable=true], [contenteditable=plaintext-only]");
    if (editing && e.key === "Escape") { endEditing(); return; }
    // Mientras se escribe: Ctrl+B, I y U dan formato a lo seleccionado, y
    // Ctrl+K pone un enlace (octubre de 2026).
    if (editing && e.target === editing && (e.ctrlKey || e.metaKey)) {
      var f = e.key.toLowerCase();
      if (f === "b" || f === "i" || f === "u") { e.preventDefault(); applyFormat(f); return; }
      if (f === "k") { e.preventDefault(); openLink(); return; }
    }
    if ((e.ctrlKey || e.metaKey) && !typing) {
      var k = e.key.toLowerCase();
      // El zoom de la hoja, no el de la página.
      if (k === "+" || k === "=") { e.preventDefault(); stepZoom(1); return; }
      if (k === "-") { e.preventDefault(); stepZoom(-1); return; }
      if (k === "0") { e.preventDefault(); fitZoom(); return; }
      if (k === "z" && !e.shiftKey) { e.preventDefault(); undo(); return; }
      if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); redo(); return; }
      if (k === "a") { e.preventDefault(); pick(doc.items.map(function (x, i) { return i; })); render(); return; }
      if (!picked.length) return;
      if (k === "c" || k === "x") {
        e.preventDefault();
        copyPicked();
        if (k === "x") { dropPicked(); render(); commit(); }
        return;
      }
      if (k === "d") { e.preventDefault(); duplicate(chosen()); return; }
      return;
    }
    if (typing || !picked.length) return;
    var step = e.shiftKey ? 10 : 1;
    if (e.key === "Delete" || e.key === "Backspace") {
      dropPicked(); render(); commit(); e.preventDefault(); return;
    }
    if (e.key === "Escape") {
      if (cropping !== null) { stopCrop(); return; }
      pick(null); render(); return;
    }
    var moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!moves[e.key]) return;
    e.preventDefault();
    // Lo elegido se mueve junto, y lo que no deja salirse es la caja que los
    // abarca: si no, el de la orilla se quedaría atrás.
    var list = chosen(), box = around(list);
    var mx = clamp(moves[e.key][0], -box.x, W - (box.x + box.w));
    var my = clamp(moves[e.key][1], -box.y, doc.h - (box.y + box.h));
    list.forEach(function (one) { one.x += mx; one.y += my; });
    list.forEach(fitRot);
    render(); commitSoon();
  });

  /* -------------------------------------------------------- recortar */

  /* Recortar no toca la foto subida: se guarda qué pedazo se ve (`crop`, de 0
     a 1) y el correo se arma con eso, así que se puede cambiar mañana.

     Mientras se recorta, la caja de la foto enseña la foto entera y encima va
     un recuadro. **El recuadro guarda la proporción de la caja**, así que lo
     que se ve nunca sale deformado: solo más cerca o más lejos. */

  /* Dónde queda la foto entera dentro de su caja, que es sobre lo que se
     dibuja el recuadro. */
  function photoBox(one) {
    var r = one.r || (one.w / Math.max(one.h, 1));
    var w = one.w, h = Math.round(one.w / r);
    if (h > one.h) { h = one.h; w = Math.round(one.h * r); }
    return { x: one.x + Math.round((one.w - w) / 2),
             y: one.y + Math.round((one.h - h) / 2), w: w, h: h };
  }

  function cropOf(one) {
    return one.crop ? one.crop.slice() : [0, 0, 1, 1];
  }

  function cropLayer(sheet) {
    var one = doc.items[cropping];
    if (!one || one.t !== "image") { cropping = null; return; }
    var seat = photoBox(one), cut = cropOf(one);

    var layer = document.createElement("div");
    layer.className = "cv-crop";
    layer.setAttribute("data-crop", "");
    layer.style.left = seat.x + "px";
    layer.style.top = seat.y + "px";
    layer.style.width = seat.w + "px";
    layer.style.height = seat.h + "px";
    layer.style.backgroundImage = "url('/img/" + encodeURIComponent(one.name) + "')";

    var frame = document.createElement("div");
    frame.className = "cv-crop__frame";
    frame.setAttribute("data-crop-frame", "");
    frame.style.left = (cut[0] * seat.w) + "px";
    frame.style.top = (cut[1] * seat.h) + "px";
    frame.style.width = (cut[2] * seat.w) + "px";
    frame.style.height = (cut[3] * seat.h) + "px";
    CORNERS.forEach(function (where) {
      var h = document.createElement("span");
      h.className = "cv-handle cv-handle--" + where;
      h.setAttribute("data-crop-handle", where);
      frame.appendChild(h);
    });
    layer.appendChild(frame);
    sheet.appendChild(layer);
  }

  /* El recuadro, en fracciones de la foto, con la proporción de la caja y sin
     salirse ni quedar más chico que un veinteavo. */
  function cropFrom(one, box) {
    var seat = photoBox(one);
    var ratio = one.w / Math.max(one.h, 1);
    var w = clamp(box.w, seat.w * 0.05, seat.w);
    var h = w / ratio;
    if (h > seat.h) { h = seat.h; w = h * ratio; }
    var x = clamp(box.x, 0, seat.w - w), y = clamp(box.y, 0, seat.h - h);
    return [+(x / seat.w).toFixed(4), +(y / seat.h).toFixed(4),
            +(w / seat.w).toFixed(4), +(h / seat.h).toFixed(4)];
  }

  function stopCrop() {
    if (cropping === null) return;
    cropping = null;
    render(); commit();
  }

  /* ----------------------------------------------------- copiar y pegar */

  /* Lo copiado viaja como texto nuestro en el portapapeles, así que se pega
     también en otra plantilla o en otra pestaña. Si el navegador no deja
     escribirlo, queda en `bench`, que sirve dentro de esta página. */
  var MARK = "sobreala-lienzo";

  function copyPicked() {
    if (!picked.length) return;
    bench = { pm: MARK, items: chosen().map(clone) };
    var text = JSON.stringify(bench);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { say(S.copied); },
                                                 function () { say(S.copied); });
        return;
      }
    } catch (err) { /* sin portapapeles queda lo de `bench` */ }
    say(S.copied);
  }

  /* Pegar lo que sea nuestro: se rehace elemento por elemento y se deja un
     poco más abajo. El servidor lo revisa igual al guardar. */
  function pasteDoc(data) {
    if (!data || data.pm !== MARK || !data.items || !data.items.length) return false;
    var fine = data.items.filter(function (one) {
      return one && (one.t === "text" || one.t === "button"
                     || one.t === "image" || one.t === "shape");
    });
    if (!fine.length) return false;
    say("");
    duplicate(fine);
    return true;
  }

  function readPaste(text) {
    try { return JSON.parse(text); } catch (err) { return null; }
  }

  document.addEventListener("paste", function (e) {
    // Mientras se escribe un texto, pegar es del texto: eso lo atiende el
    // manejador del lienzo, que mete lo pegado como texto plano.
    if (editing) return;
    var target = e.target.closest && e.target.closest("input, textarea, select");
    if (target) return;
    var data = e.clipboardData || window.clipboardData;
    if (!data) return;

    // Una foto pegada llega en `files` o en `items`, según el navegador y de
    // dónde se copió: se miran los dos.
    var photos = [];
    if (data.files && data.files.length) {
      Array.prototype.forEach.call(data.files, function (f) {
        if (f && f.type.indexOf("image/") === 0) photos.push(f);
      });
    }
    if (!photos.length && data.items) {
      Array.prototype.forEach.call(data.items, function (one) {
        if (one.kind !== "file" || one.type.indexOf("image/") !== 0) return;
        var f = one.getAsFile();
        if (f) photos.push(f);
      });
    }
    if (photos.length) {
      e.preventDefault();
      // De a una: cada una pasa por la misma revisión que subir un archivo.
      photos.slice(0, 3).forEach(function (file) { sendImage(file, null, visibleCenter()); });
      return;
    }
    var text = data.getData ? data.getData("text/plain") : "";
    if (text && pasteDoc(readPaste(text))) { e.preventDefault(); return; }
    // Una imagen copiada de una página suele llegar solo como dirección. No se
    // va a buscar: el servidor no pide imágenes a otros sitios.
    var html = data.getData ? data.getData("text/html") : "";
    if ((html && html.indexOf("<img") >= 0) || /^https?:\/\/\S+\.(png|jpe?g|gif|webp)/i.test(text || "")) {
      e.preventDefault();
      say(S.pasteUrl);
      return;
    }
    // Si el navegador no dejó escribir en el portapapeles, lo copiado sigue
    // aquí dentro.
    if (bench && pasteDoc(bench)) e.preventDefault();
  });

  root.addEventListener("click", function (e) {
    var b = e.target.closest("[data-add]");
    if (!b) return;
    add(b.getAttribute("data-add"), b.getAttribute("data-shape"), b.getAttribute("data-preset"));
    // En el teléfono el panel tapa la hoja: se cierra al agregar.
    if (window.innerWidth <= 760 && rail) openPanel("");
  });
  document.querySelector("[data-undo]").addEventListener("click", undo);
  document.querySelector("[data-redo]").addEventListener("click", redo);

  /* ------------------------------------------------ guardar y vista previa */

  /* Guardar siempre guarda (octubre de 2026): lo que no cumple las reglas se
     guarda como borrador, que no se puede enviar. Lo encimado y lo que falta
     se siguen marcando en la hoja y en la revisión. */
  saveForm.addEventListener("submit", function (e) {
    if (editing) editing.blur();
    if (!nameField.value.trim()) {
      e.preventDefault(); say(S.nameNeeded); nameField.focus(); return;
    }
    saveForm.querySelector("[name=lienzo]").value = JSON.stringify(doc);
    dirty = false;
  });

  /* La barra de peso y la revisión antispam. Las pide al servidor, que hace
     la misma cuenta que al guardar; mientras haya un motivo, Guardar dice
     «Guardar borrador» (octubre de 2026). */
  var check = document.querySelector("[data-canvas-check]");
  var saveButton = document.querySelector("[data-canvas-submit]");
  function runCheck() {
    if (!check) return;
    var body = new FormData();
    body.append("csrf_token", saveForm.querySelector("[name=csrf_token]").value);
    body.append("lienzo", JSON.stringify(doc));
    // El nombre, para la regla del nombre de la ventana de requisitos.
    body.append("nombre", nameField.value);
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
        check.querySelector("[data-check-bad]").hidden = answer.ok;
        check.querySelector("[data-check-ok]").hidden = !answer.ok;
        // El punto del ícono de Revisión: le falta algo para enviarse.
        var dot = document.querySelector("[data-review-dot]");
        if (dot) {
          dot.hidden = answer.ok;
          dot.parentNode.title = answer.ok ? S.reviewOk : S.reviewBad;
        }
        saveButton.textContent = answer.ok ? S.save : S.saveDraft;
        saveButton.title = answer.ok ? "" : S.saveDraftHint;
        fillRules(answer.rules || []);
      })
      .catch(function () { /* sin revisión no se bloquea: el servidor revisa igual */ });
  }

  /* La ventana de requisitos: todas las reglas, cada una con ✓ o ✕ y su frase,
     en su grupo. Las frases y las cifras las pone el servidor, que es quien
     decide si se guarda. */
  var rulesDialog = document.querySelector("[data-rules-dialog]");
  function fillRules(rules) {
    if (!rulesDialog || !rules.length) return;
    var met = 0;
    ["build", "spam"].forEach(function (group) {
      var list = rulesDialog.querySelector('[data-rules="' + group + '"]');
      list.textContent = "";
      rules.forEach(function (rule) {
        if (rule.group !== group) return;
        if (rule.ok) met += 1;
        var li = document.createElement("li");
        li.className = "rules__one " + (rule.ok ? "is-ok" : "is-bad");
        var mark = document.createElement("span");
        mark.className = "rules__mark";
        mark.setAttribute("aria-hidden", "true");
        mark.textContent = rule.ok ? "✓" : "✕";
        var text = document.createElement("span");
        // El lector de pantalla no lee la marca: lee «Cumple:» o «No cumple:».
        var said = document.createElement("span");
        said.className = "visually-hidden";
        said.textContent = (rule.ok ? S.ruleYes : S.ruleNo) + " ";
        text.appendChild(said);
        text.appendChild(document.createTextNode(rule.text));
        li.appendChild(mark);
        li.appendChild(text);
        list.appendChild(li);
      });
    });
    rulesDialog.querySelector("[data-rules-count]").textContent =
      S.rulesCount.replace("{ok}", met).replace("{n}", rules.length);
  }
  // Al abrirla se pide una revisión al momento, y escribir el nombre también
  // la pide: es una de las reglas.
  var rulesOpener = document.querySelector('[data-open-dialog="requisitos"]');
  if (rulesOpener) rulesOpener.addEventListener("click", runCheck);
  var nameTimer = null;
  nameField.addEventListener("input", function () {
    clearTimeout(nameTimer);
    nameTimer = setTimeout(runCheck, 500);
  });

  /* Con quién se ve: los nombres de las columnas, o los datos de un contacto. */
  var person = document.querySelector("[data-preview-contact]");
  var previewDialog = document.querySelector("[data-preview-dialog]");

  function sendPreview() {
    previewForm.querySelector("[name=lienzo]").value = JSON.stringify(doc);
    previewForm.querySelector("[name=contacto]").value = person ? person.value : "";
    previewForm.submit();
  }
  if (person) person.addEventListener("change", sendPreview);

  /* La vista previa vive en su ventana: **cerrada no se le pide nada al
     servidor**, y al abrirla se refresca con lo que haya en ese momento. La
     revisión antispam sí corre siempre: es la que no deja guardar, y esconder
     por qué está apagado el botón sería esconderlo. */
  function previewOpen() {
    return !previewDialog || previewDialog.open;
  }

  if (previewDialog) {
    var opener = document.querySelector('[data-open-dialog="vista-previa"]');
    if (opener) opener.addEventListener("click", function () { sendPreview(); });
  }

  /* Bajarse la pieza en PDF: lo mismo que la vista previa, con su formulario y
     sin marco. La respuesta es un archivo que el navegador baja, así que la
     página se queda donde está. */
  function downloader(button, form) {
    var send = document.querySelector(button);
    var papers = document.querySelector(form);
    if (!send || !papers) return;
    send.addEventListener("click", function () {
      var named = nameField;
      papers.querySelector("[name=lienzo]").value = JSON.stringify(doc);
      papers.querySelector("[name=nombre]").value = named ? named.value : "";
      papers.submit();
    });
  }
  downloader("[data-canvas-pdf]", "[data-canvas-pdf-form]");

  /* El HTML es un enlace a la plantilla guardada, lista para volver a cargarla:
     sus imágenes fundidas solo existen al guardar. Sin guardar todavía, o con
     cambios sin guardar, lo de pantalla no está en el archivo, y se dice en vez
     de bajar otra cosa. */
  var htmlLink = document.querySelector("[data-canvas-html]");
  if (htmlLink) {
    htmlLink.addEventListener("click", function (e) {
      if (htmlLink.tagName === "A" && !dirty) { say(""); return; }
      e.preventDefault();
      say(S.htmlSaveFirst);
    });
  }

  var previewTimer = null;
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      if (previewOpen()) sendPreview();
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

  checkFit();
  render();
  fitZoom();
  past.push(JSON.stringify(doc));
  learnRatios();
  schedulePreview();
})();
