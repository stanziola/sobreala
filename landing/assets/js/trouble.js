/* Los cuatro puntos de «El problema», en la portada. Sin dependencias, como
   nav.js.

   El bloque funciona entero sin este archivo: lo que abre cada punto son
   botones de radio, así que se pulsa con el ratón, se mueve con las flechas del
   teclado y se ve igual de bien. Lo de aquí es un añadido: pasar al siguiente
   solo.

   **El reloj es la barra del pie de la tarjeta abierta**, una animación de CSS
   que dura --trouble-every (site.css). Este archivo no cuenta el tiempo: espera
   a que la barra se llene (`animationend`) y abre el siguiente, así que la
   barra y el cambio no se pueden separar. Lo que hace es poner dos clases en el
   bloque: `is-playing`, con el paso automático encendido (y la barra a la
   vista), e `is-paused`, cuando se detiene un momento (la barra se queda donde
   iba y sigue desde ahí). Hubo otra barra en septiembre de 2026 que corría
   aparte de un `setInterval` de aquí: con el ratón encima el cambio se pausaba
   y ella seguía llenándose.

   **Si alguien lo cambia a mano, espera tres segundos** en el punto que eligió,
   con su barra vacía, y después sigue solo desde ahí. Otro cambio antes de
   tiempo vuelve a empezar la espera. Hasta octubre de 2026 un cambio a mano lo
   apagaba para el resto de la visita, y el ratón encima o el foco dentro lo
   pausaban: al pulsar, el ratón se queda encima y no volvía a andar nunca.

   No corre fuera de la pantalla ni con la pestaña escondida, y con «reducir
   movimiento» puesto no existe: quien lo pide no quiere que la página se mueva
   mientras lee.

   Estas reglas son las mismas que las de stories.js, con su propia espera, y
   están repetidas a propósito: cada archivo se lee por su cuenta y tocar uno no
   puede romper el otro. */
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

  /* Lo que espera después de un cambio a mano, con la barra vacía. */
  var WAIT = 3000;
  var seen = !window.IntersectionObserver;   // sin observador, se da por visto
  var away = false;                          // la pestaña, escondida
  var hold = null;                           // la espera tras un cambio a mano

  function sync() {
    var on = !quiet.matches;
    block.classList.toggle("is-playing", on);
    block.classList.toggle("is-paused", !(on && seen && !away && !hold));
  }

  /* El punto nuevo estrena su animación, así que en pausa su barra queda vacía;
     al acabar la espera empieza a llenarse desde cero. */
  function wait() {
    window.clearTimeout(hold);
    hold = window.setTimeout(function () { hold = null; sync(); }, WAIT);
    sync();
  }

  /* La barra se llenó: toca el siguiente. La suya empieza de cero sola, porque
     la animación solo la lleva la tarjeta abierta. */
  block.addEventListener("animationend", function (event) {
    if (event.animationName === "trouble-fill") open(current() + 1);
  });

  /* `change` solo salta cuando el radio lo cambia una persona (pulsando un
     punto o con las flechas del teclado), nunca cuando lo marca este guion: así
     se distingue un cambio a mano de uno automático sin llevar la cuenta. */
  picks.forEach(function (pick) {
    pick.addEventListener("change", wait);
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
