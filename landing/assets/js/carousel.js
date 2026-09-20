/* El carrusel de capturas de la portada. Sin dependencias, como nav.js.

   La sección funciona entera sin este archivo: lo que abre cada captura son
   botones de radio, así que se pulsa con el ratón, se mueve con las flechas
   del teclado y en el teléfono se ven las seis con su texto. Lo de aquí son
   dos añadidos: los botones de anterior y siguiente, que solo se dibujan si
   este archivo corrió, y el paso automático.

   Con «reducir movimiento» puesto no pasa sola: quien lo pide no quiere que
   la página se mueva mientras lee. */
(function () {
  "use strict";

  var tour = document.querySelector("[data-tour]");
  if (!tour) return;

  var picks = Array.prototype.slice.call(tour.querySelectorAll(".tour__pick"));
  var back = tour.querySelector("[data-tour-back]");
  var next = tour.querySelector("[data-tour-next]");
  if (picks.length < 2 || !back || !next) return;

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

  /* Siete segundos: lo que tarda en leerse el texto de una, y bastante para
     que no parezca que la página parpadea. */
  var EVERY = 7000;
  var timer = null;
  var stopped = quiet.matches;

  function play() {
    if (stopped || timer) return;
    timer = window.setInterval(function () {
      open(current() + 1);
    }, EVERY);
  }

  function pause() {
    if (!timer) return;
    window.clearInterval(timer);
    timer = null;
  }

  // Elegir una a mano lo apaga del todo: a quien ya está mirando la que quiso
  // no se le cambia debajo. Pasar el ratón por encima solo lo detiene mientras.
  function stop() {
    stopped = true;
    pause();
  }

  tour.addEventListener("pointerenter", pause);
  tour.addEventListener("pointerleave", play);
  tour.addEventListener("focusin", pause);
  tour.addEventListener("focusout", play);
  tour.addEventListener("click", stop);
  picks.forEach(function (pick) {
    pick.addEventListener("change", stop);
  });

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) pause();
    else play();
  });

  // Fuera de la pantalla tampoco corre: nadie la está viendo.
  if (window.IntersectionObserver) {
    new window.IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) play();
        else pause();
      });
    }, { threshold: 0.35 }).observe(tour);
  } else {
    play();
  }

  /* -------------------------------------------------------------- las flechas */

  back.addEventListener("click", function () {
    open(current() - 1);
  });
  next.addEventListener("click", function () {
    open(current() + 1);
  });
})();
