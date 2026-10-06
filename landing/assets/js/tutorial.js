/* Los tutoriales de /how-it-works. Sin dependencias, como carousel.js.

   Sin este archivo la sección se lee entera: cada recorrido con todos sus pasos,
   uno debajo del otro. Con él es un reproductor: un recorrido a la vez, un paso
   a la vez, y pulsar el anillo (o Enter con él enfocado) pasa al siguiente, que
   es lo que el panel enseña después de ese clic. El globo va junto al anillo en
   pantallas anchas, del lado que tenga sitio.

   La pestaña viaja en la dirección (#contactos, #plantillas…), así se puede
   mandar el enlace de un tutorial. Con «reducir movimiento» no late ni se
   funde: eso lo resuelve el CSS. */
(function () {
  "use strict";

  var root = document.querySelector("[data-tutorial]");
  if (!root) return;

  var guides = Array.prototype.slice.call(root.querySelectorAll("[data-guide]"));
  var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-tab]"));
  var status = root.querySelector("[data-tutorial-status]");
  var controls = root.querySelector("[data-controls]");
  if (!guides.length) return;

  var wide = window.matchMedia("(min-width: 900px)");
  var tour = 0;
  var step = 0;

  root.classList.add("is-ready");
  controls.hidden = false;
  Array.prototype.forEach.call(root.querySelectorAll("[data-again], [data-finish]"),
                               function (el) { el.hidden = false; });

  // Las pestañas, como pestañas.
  var nav = root.querySelector(".tutorial__tabs");
  nav.setAttribute("role", "tablist");
  tabs.forEach(function (tab) {
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", tab.dataset.tab);
  });
  guides.forEach(function (guide) { guide.setAttribute("role", "tabpanel"); });

  // Los anillos, como botones.
  Array.prototype.forEach.call(root.querySelectorAll("[data-spot]"), function (ring) {
    ring.setAttribute("role", "button");
    ring.setAttribute("tabindex", "0");
    ring.setAttribute("aria-label", ring.dataset.label);
  });

  function stepsOf(index) {
    return Array.prototype.slice.call(guides[index].querySelectorAll("[data-step], [data-done]"));
  }

  function dark() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  // La captura que se ve de un paso, que es la del tema puesto.
  function shotOf(item) {
    return item.querySelector(dark() ? ".guide-step__shot--dark" : ".guide-step__shot--light");
  }

  /* Adelantar la captura del paso siguiente, para que al pulsar ya esté: las
     demás siguen perezosas y no cuestan nada hasta que se ven. */
  function preload(item) {
    var shot = item && shotOf(item);
    if (shot) shot.loading = "eager";
  }

  function clamp(n, low, high) { return Math.max(low, Math.min(high, n)); }

  /* El globo junto al anillo: a la derecha si cabe, si no a la izquierda, y si
     no cabe a ningún lado, debajo o encima. Sin anillo (el último paso), en
     medio de la captura, abajo. En pantallas angostas va debajo, en el flujo. */
  /* En el teléfono, correr la captura agrandada hasta dejar el anillo en
     medio, sin pasarse de sus bordes. */
  function pan(item) {
    var zoom = item.querySelector("[data-zoom]");
    if (!zoom) return;
    var ring = item.querySelector("[data-spot]");
    if (wide.matches || !ring) { zoom.style.removeProperty("--pan"); return; }
    var W = item.querySelector("[data-frame]").clientWidth;
    var center = (parseFloat(ring.style.getPropertyValue("--x")) +
                  parseFloat(ring.style.getPropertyValue("--w")) / 2) / 100 * 2 * W;
    zoom.style.setProperty("--pan", clamp(W / 2 - center, -W, 0) + "px");
  }

  function place(item) {
    pan(item);
    var tip = item.querySelector("[data-tip]");
    if (!tip) return;
    tip.removeAttribute("data-side");
    tip.style.left = tip.style.top = "";
    tip.style.removeProperty("--arrow");
    if (!wide.matches) return;

    var screen = item.querySelector("[data-screen]");
    var ring = item.querySelector("[data-spot]");
    var W = screen.clientWidth, H = shotOf(item).clientHeight || screen.clientHeight;
    tip.setAttribute("data-side", "middle");
    var tw = tip.offsetWidth, th = tip.offsetHeight, gap = 20, edge = 10;

    if (!ring) {
      tip.style.left = (W - tw) / 2 + "px";
      tip.style.top = Math.max(edge, H - th - 24) + "px";
      return;
    }
    var box = ring.getBoundingClientRect(), frame = screen.getBoundingClientRect();
    var x = box.left - frame.left, y = box.top - frame.top;
    var w = box.width, h = box.height, side, left, top;

    if (x + w + gap + tw <= W - edge) {
      side = "right"; left = x + w + gap;
    } else if (x - gap - tw >= edge) {
      side = "left"; left = x - gap - tw;
    }
    if (side) {
      top = clamp(y + h / 2 - th / 2, edge, H - th - edge);
      tip.style.setProperty("--arrow", clamp(y + h / 2 - top, 18, th - 18) + "px");
    } else {
      left = clamp(x + w / 2 - tw / 2, edge, W - tw - edge);
      if (y + h + gap + th <= H - edge) {
        side = "below"; top = y + h + gap;
      } else {
        side = "above"; top = Math.max(edge, y - gap - th);
      }
      tip.style.setProperty("--arrow", clamp(x + w / 2 - left, 18, tw - 18) + "px");
    }
    tip.setAttribute("data-side", side);
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  /* Que el anillo y su globo se vean: si quedan debajo de la barra fija del
     sitio o fuera de la ventana, la página se mueve lo justo. */
  var quiet = window.matchMedia("(prefers-reduced-motion: reduce)");
  function reveal(item) {
    var parts = [item.querySelector("[data-spot]"), item.querySelector("[data-tip]")]
      .filter(Boolean).map(function (el) { return el.getBoundingClientRect(); });
    if (!parts.length) return;
    var top = Math.min.apply(null, parts.map(function (r) { return r.top; }));
    var bottom = Math.max.apply(null, parts.map(function (r) { return r.bottom; }));
    var bar = document.querySelector(".site-header");
    var roof = (bar ? bar.getBoundingClientRect().bottom : 0) + 16;
    var floor = window.innerHeight - 16;
    var move = 0;
    if (top < roof) move = top - roof;
    else if (bottom > floor) move = Math.min(bottom - floor, top - roof);
    if (move) window.scrollBy({ top: move, behavior: quiet.matches ? "auto" : "smooth" });
  }

  function say(item) {
    var count = item.querySelector(".guide-step__count");
    var todo = item.querySelector(".guide-step__do");
    var done = item.querySelector(".guide-done__title");
    status.textContent = count ? count.textContent + ". " + todo.textContent
                               : (done ? done.textContent : "");
  }

  /* Enseñar un paso. `focus` mueve el foco a su anillo: al pulsar con el
     teclado, el anillo anterior desaparece y el foco no puede quedarse en el
     aire. Al elegir una pestaña no, que el foco está en la pestaña. */
  function show(t, s, focus, moved) {
    tour = t;
    var items = stepsOf(t);
    step = clamp(s, 0, items.length - 1);
    guides.forEach(function (guide, i) { guide.classList.toggle("is-current", i === t); });
    tabs.forEach(function (tab, i) {
      tab.setAttribute("aria-selected", i === t ? "true" : "false");
      tab.setAttribute("tabindex", i === t ? "0" : "-1");
    });
    items.forEach(function (item, i) { item.classList.toggle("is-shown", i === step); });
    var item = items[step];
    var shot = shotOf(item);
    if (shot) {
      shot.loading = "eager";
      if (!shot.complete) shot.addEventListener("load", function () { place(item); }, { once: true });
    }
    place(item);
    preload(items[step + 1]);
    say(item);
    root.querySelector("[data-back]").disabled = step === 0;
    if (moved) reveal(item);
    if (focus) {
      var target = item.querySelector("[data-spot], [data-finish], [data-again]");
      if (target) target.focus({ preventScroll: true });
    }
  }

  function next(focus) { show(tour, step + 1, focus, true); }

  function open(id, scroll) {
    var index = guides.findIndex(function (guide) { return guide.dataset.guide === id; });
    if (index < 0) return false;
    show(index, 0, false);
    if (history.replaceState) history.replaceState(null, "", "#" + id);
    if (scroll) root.scrollIntoView({ block: "start" });
    return true;
  }

  // Pulsar el anillo avanza; pulsar en otro sitio de la captura lo hace latir.
  root.addEventListener("click", function (event) {
    var target = event.target;
    if (target.closest("[data-spot]")) {
      next(event.detail === 0);
      return;
    }
    var tab = target.closest("[data-tab]");
    if (tab) {
      event.preventDefault();
      open(tab.dataset.tab, false);
      return;
    }
    var jump = target.closest("[data-goto]");
    if (jump) {
      event.preventDefault();
      open(jump.dataset.goto, true);
      return;
    }
    if (target.closest("[data-finish]")) { next(true); return; }
    if (target.closest("[data-again]") || target.closest("[data-restart]")) {
      show(tour, 0, true, true);
      return;
    }
    if (target.closest("[data-back]")) { show(tour, step - 1, false, true); return; }
    var screen = target.closest("[data-screen]");
    var ring = screen && screen.querySelector("[data-spot]");
    if (ring && !target.closest("[data-tip]")) {
      ring.classList.remove("is-nudge");
      void ring.offsetWidth;  // volver a empezar la animación
      ring.classList.add("is-nudge");
    }
  });

  root.addEventListener("keydown", function (event) {
    var ring = event.target.closest && event.target.closest("[data-spot]");
    if (ring && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      next(true);
      return;
    }
    // Las flechas mueven entre pestañas, como en cualquier lista de pestañas.
    var tab = event.target.closest && event.target.closest("[data-tab]");
    if (tab && (event.key === "ArrowRight" || event.key === "ArrowLeft")) {
      event.preventDefault();
      var to = (tour + (event.key === "ArrowRight" ? 1 : -1) + guides.length) % guides.length;
      open(guides[to].dataset.guide, false);
      tabs[to].focus();
    }
  });

  root.addEventListener("animationend", function (event) {
    if (event.target.classList.contains("is-nudge")) event.target.classList.remove("is-nudge");
  });

  function replace() {
    var item = stepsOf(tour)[step];
    if (item) place(item);
  }
  window.addEventListener("resize", replace);
  // Cambiar de tema cambia de captura: la nueva se baja y el globo se recoloca.
  new MutationObserver(function () { show(tour, step, false); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // Un enlace a otro tutorial dentro de la misma página cambia solo el «#».
  window.addEventListener("hashchange", function () {
    open(location.hash.slice(1), true);
  });

  var wanted = location.hash.slice(1);
  if (!(wanted && open(wanted, true))) show(0, 0, false);
})();
