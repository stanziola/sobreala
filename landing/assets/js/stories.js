/* Los cuatro casos de «Haz crecer tu negocio», en la portada. Sin
   dependencias, como nav.js.

   El bloque funciona entero sin este archivo: lo que abre cada caso son
   botones de radio y los puntos son sus etiquetas, así que se pulsa con el
   ratón, se mueve con las flechas del teclado y se ve igual de bien. Lo de
   aquí es un añadido: pasar al siguiente solo.

   **Si alguien pulsa un punto, deja de pasar solo** para el resto de la
   visita, como en «¿Sigues enviando…?»: quien elige un caso lo está mirando a
   su ritmo.

   Mientras nadie lo toque, se detiene con el ratón encima o con el foco dentro
   y vuelve a andar al quitarlo, no corre fuera de la pantalla ni con la pestaña
   escondida, y con «reducir movimiento» puesto no existe.

   Estas pausas son las mismas que las de trouble.js y están escritas otra vez
   a propósito: cada archivo se lee por su cuenta y tocar uno no puede romper
   el otro. */
(function () {
  "use strict";

  var block = document.querySelector("[data-stories]");
  if (!block) return;

  var picks = Array.prototype.slice.call(block.querySelectorAll(".stories__pick"));
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

  /* Ocho segundos: cada caso es una foto, un título y una línea. */
  var EVERY = 8000;
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
     punto o con las flechas del teclado), nunca cuando lo marca este guion. */
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
