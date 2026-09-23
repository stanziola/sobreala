/* Los cuatro puntos de «El problema», en la portada. Sin dependencias, como
   nav.js.

   El bloque funciona entero sin este archivo: lo que abre cada punto son
   botones de radio, así que se pulsa con el ratón, se mueve con las flechas del
   teclado y se ve igual de bien. Lo de aquí es un añadido: pasar al siguiente
   solo.

   **Si alguien lo cambia a mano, deja de pasar solo** para el resto de la
   visita: quien pulsa un punto está leyendo a su ritmo, y que se le cambie
   luego por su cuenta es quitarle lo que eligió. Es distinto de Features, donde
   se pidió que volviera a andar al quitar el ratón.

   Mientras nadie lo toque, se detiene con el ratón encima o con el foco dentro
   y vuelve a andar al quitarlo, no corre fuera de la pantalla ni con la pestaña
   escondida, y con «reducir movimiento» puesto no existe: quien lo pide no
   quiere que la página se mueva mientras lee.

   Estas pausas son las mismas que las del carrusel de capturas y están escritas
   dos veces a propósito: cada archivo se lee por su cuenta y tocar uno no puede
   romper el otro. Si algún día molesta, el sitio donde juntarlas es una función
   `autoplay()` que usen los dos. */
(function () {
  "use strict";

  var block = document.querySelector("[data-trouble]");
  if (!block) return;

  var picks = Array.prototype.slice.call(block.querySelectorAll(".trouble__pick"));
  if (picks.length < 2) return;

  var quiet = window.matchMedia("(prefers-reduced-motion: reduce)");

  function open(which) {
    picks[(which + picks.length) % picks.length].checked = true;
  }

  function current() {
    for (var i = 0; i < picks.length; i++) {
      if (picks[i].checked) return i;
    }
    return 0;
  }

  /* --------------------------------------------------- el paso automático */

  /* Quince segundos: cada punto trae unas 50 a 60 palabras entre el título, la
     línea corta y el párrafo, y hay que poder leerlas enteras. */
  var EVERY = 15000;
  var timer = null;
  var seen = !window.IntersectionObserver;   // sin observador, se da por visto
  var over = false;                          // el ratón o el foco, dentro
  var away = false;                          // la pestaña, escondida
  var mine = false;                          // alguien lo movió a mano

  function sync() {
    var run = !mine && seen && !over && !away && !quiet.matches;
    if (run && !timer) {
      timer = window.setInterval(function () { open(current() + 1); }, EVERY);
    } else if (!run && timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  function inside(yes) {
    return function () { over = yes; sync(); };
  }

  block.addEventListener("pointerenter", inside(true));
  block.addEventListener("pointerleave", inside(false));
  block.addEventListener("focusin", inside(true));
  block.addEventListener("focusout", inside(false));

  /* `change` solo salta cuando el radio lo cambia una persona (pulsando un
     punto o con las flechas del teclado), nunca cuando lo marca este guion: así
     se distingue un cambio a mano de uno automático sin llevar la cuenta. */
  picks.forEach(function (pick) {
    pick.addEventListener("change", function () { mine = true; sync(); });
  });

  document.addEventListener("visibilitychange", function () {
    away = document.hidden;
    sync();
  });

  // Fuera de la pantalla tampoco corre: nadie lo está mirando.
  if (window.IntersectionObserver) {
    new window.IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { seen = entry.isIntersecting; });
      sync();
    }, { threshold: 0.35 }).observe(block);
  }
  sync();
})();
