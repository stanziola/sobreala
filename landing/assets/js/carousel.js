/* El carrusel de Features. Sin dependencias, como nav.js.

   La sección funciona entera sin este archivo: lo que abre cada dibujo son
   botones de radio, así que se pulsa con el ratón, se mueve con las flechas
   del teclado y en el teléfono se ven los cinco con su texto. Lo de aquí son
   dos añadidos, y ninguno existe sin este archivo: los botones de anterior y
   siguiente, y el paso automático (que se detiene con el ratón encima y vuelve
   a andar al quitarlo).

   Hubo además una ventana para ver una captura en grande, y se quitó con las
   capturas: los dibujos de ahora se leen enteros en su sitio.

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

  /* Cuatro segundos: lo que se tarda en mirar un dibujo. Con cinco, la vuelta
     entera dura veinte. */
  var EVERY = 4000;
  var timer = null;

  /* Tres interruptores y un solo sitio que decide. Antes cada uno llamaba a
     `play()` por su cuenta y el ratón podía arrancarlo con la sección fuera de
     la pantalla. */
  var seen = !window.IntersectionObserver;   // sin observador, se da por vista
  var over = false;                          // el ratón o el foco, dentro
  var away = false;                          // la pestaña, escondida

  function sync() {
    // Quien pidió no ver movimiento no lo ve: ahí no pasa sola nunca.
    var run = seen && !over && !away && !quiet.matches;
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
})();
