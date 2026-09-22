/* El carrusel de capturas de la portada. Sin dependencias, como nav.js.

   La sección funciona entera sin este archivo: lo que abre cada captura son
   botones de radio, así que se pulsa con el ratón, se mueve con las flechas
   del teclado y en el teléfono se ven las cinco con su texto. Lo de aquí son
   tres añadidos, y ninguno existe sin este archivo: los botones de anterior y
   siguiente, el paso automático (que se detiene con el ratón encima y vuelve a
   andar al quitarlo) y la ventana de ver una captura en grande.

   Con «reducir movimiento» puesto no pasa sola: quien lo pide no quiere que
   la página se mueva mientras lee. */
(function () {
  "use strict";

  var tour = document.querySelector("[data-tour]");
  if (!tour) return;

  var picks = Array.prototype.slice.call(tour.querySelectorAll(".tour__pick"));
  var strip = tour.querySelector(".tour__strip");
  var back = tour.querySelector("[data-tour-back]");
  var next = tour.querySelector("[data-tour-next]");
  if (picks.length < 2 || !strip || !back || !next) return;

  var quiet = window.matchMedia("(prefers-reduced-motion: reduce)");

  // Las flechas solo existen si este archivo corrió.
  tour.classList.add("is-ready");

  function open(which) {
    var to = (which + picks.length) % picks.length;
    picks[to].checked = true;
  }

  function current() {
    for (var i = 0; i < picks.length; i++) {
      if (picks[i].checked) return i;
    }
    return 0;
  }

  /* ------------------------------------------------------ el paso automático */

  /* Cuatro segundos: lo que se tarda en mirar una captura. Con cinco, la vuelta
     entera dura veinte. */
  var EVERY = 4000;
  var timer = null;

  /* Tres interruptores y un solo sitio que decide. Antes cada uno llamaba a
     `play()` por su cuenta y el ratón podía arrancarlo con la sección fuera de
     la pantalla. */
  var seen = !window.IntersectionObserver;   // sin observador, se da por vista
  var over = false;                          // el ratón o el foco, dentro
  var away = false;                          // la pestaña, escondida
  var big = false;                           // una captura, abierta en grande

  function sync() {
    // Quien pidió no ver movimiento no lo ve: ahí no pasa sola nunca.
    var run = seen && !over && !away && !big && !quiet.matches;
    if (run && !timer) {
      timer = window.setInterval(function () { open(current() + 1); }, EVERY);
    } else if (!run && timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  /* Elegir una a mano **no lo apaga**: solo vuelve a empezar la cuenta, para
     que la que se acaba de pulsar no se cambie medio segundo después. */
  function restart() {
    if (!timer) return;
    window.clearInterval(timer);
    timer = null;
    sync();
  }

  function inside(yes) {
    return function () { over = yes; sync(); };
  }

  tour.addEventListener("pointerenter", inside(true));
  tour.addEventListener("pointerleave", inside(false));
  tour.addEventListener("focusin", inside(true));
  tour.addEventListener("focusout", inside(false));
  picks.forEach(function (pick) {
    pick.addEventListener("change", restart);
  });

  document.addEventListener("visibilitychange", function () {
    away = document.hidden;
    sync();
  });

  // Fuera de la pantalla tampoco corre: nadie la está viendo.
  if (window.IntersectionObserver) {
    new window.IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { seen = entry.isIntersecting; });
      sync();
    }, { threshold: 0.35 }).observe(tour);
  }
  sync();

  /* -------------------------------------------------------------- las flechas */

  back.addEventListener("click", function () {
    open(current() - 1);
  });
  next.addEventListener("click", function () {
    open(current() + 1);
  });

  /* ------------------------------------------------- la captura en grande */

  /* Un <dialog> y no un invento propio: de ahí salen gratis el Escape, el foco
     atrapado dentro, el fondo oscurecido y el foco de vuelta al listón al
     cerrarla. Si el navegador no lo trae, no hay zoom y lo demás sigue igual. */
  var box = document.createElement("dialog");
  if (!box.showModal) return;

  var CLOSE_ICON =
    '<svg class="icon" viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
    'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="m6 6 12 12"/><path d="m18 6-12 12"/></svg>';

  box.className = "tour__zoom";
  box.setAttribute("aria-label", tour.getAttribute("data-tour-zoom") || "");
  box.innerHTML =
    '<img class="tour__zoom-shot" alt="">' +
    '<button class="tour__zoom-close" type="button">' + CLOSE_ICON + "</button>";
  var huge = box.querySelector(".tour__zoom-shot");
  var shut = box.querySelector(".tour__zoom-close");
  shut.setAttribute("aria-label", tour.getAttribute("data-tour-close") || "");
  tour.appendChild(box);

  /* Apilado no hay una abierta y otras cerradas: se ven las cinco, así que
     cualquiera se agranda. Se le pregunta al CSS en vez de repetir aquí el
     ancho del corte, que ya está escrito en site.css. */
  function stacked() {
    return window.getComputedStyle(strip).display === "contents";
  }

  // La que se ve, que es la del tema puesto: la otra está en display:none.
  function shown(panel) {
    var shots = panel.querySelectorAll(".tour__shot");
    for (var i = 0; i < shots.length; i++) {
      if (shots[i].offsetParent !== null) return shots[i];
    }
    return shots[0] || null;
  }

  /* A dónde vuelve el foco al cerrar: al botón de radio de esa captura, que es
     el que mueve el carrusel con las flechas del teclado. La etiqueta no sirve,
     porque no se puede enfocar. */
  var from = null;

  strip.addEventListener("click", function (event) {
    var panel = event.target.closest ? event.target.closest(".tour__panel") : null;
    if (!panel) return;
    var seat = Array.prototype.indexOf.call(strip.children, panel);
    // Una cerrada de la tira se abre, que es la navegación de siempre.
    if (seat < 0 || (!stacked() && !picks[seat].checked)) return;

    var shot = shown(panel);
    if (!shot) return;
    // Cortar el clic de la etiqueta, que si no vuelve a marcar su radio.
    event.preventDefault();
    huge.src = shot.currentSrc || shot.src;
    huge.alt = shot.alt;
    from = picks[seat];
    big = true;
    sync();
    box.showModal();
  });

  shut.addEventListener("click", function () { box.close(); });

  // Pulsar el borde de alrededor, que es el propio diálogo, también cierra.
  box.addEventListener("click", function (event) {
    if (event.target === box) box.close();
  });

  box.addEventListener("close", function () {
    big = false;
    sync();
    if (from && from.focus) from.focus();
    from = null;
  });
})();
