/* Los cuatro casos de «Haz crecer tu negocio», en la portada. Sin
   dependencias, como nav.js.

   El bloque funciona entero sin este archivo: lo que abre cada caso son
   botones de radio y las barras de abajo son sus etiquetas, así que se pulsa
   con el ratón, se mueve con las flechas del teclado y se ve igual de bien. Lo
   de aquí son dos añadidos, y ninguno existe sin este archivo: las flechas de
   los lados de las barras, y pasar al siguiente solo.

   **El reloj es la barra del caso abierto**, una animación de CSS que dura
   --stories-every (site.css), como en «¿Sigues enviando…?»: este archivo
   espera a que se llene (`animationend`) y abre el siguiente. Pone tres clases
   en el bloque: `is-ready`, porque corrió (y con ella se ven las flechas);
   `is-playing`, con el paso automático encendido (y la barra llenándose); e
   `is-paused`, cuando se detiene un momento (la barra se queda donde iba).

   **Si alguien pulsa una barra o una flecha, espera un segundo** con la barra
   del caso nuevo gris, y después el azul empieza a llenarla otra vez. Otro
   cambio antes de tiempo vuelve a empezar la espera. Hasta octubre de 2026 un
   cambio a mano lo apagaba con la barra azul y llena, y el ratón encima o el
   foco dentro lo pausaban: al pulsar, el ratón se queda encima y no volvía a
   andar nunca.

   No corre fuera de la pantalla ni con la pestaña escondida, y con «reducir
   movimiento» puesto no existe. Las flechas, sí.

   Estas reglas son las mismas que las de trouble.js, con su propia espera, y
   están escritas otra vez a propósito: cada archivo se lee por su cuenta y
   tocar uno no puede romper el otro. */
(function () {
  "use strict";

  var block = document.querySelector("[data-stories]");
  if (!block) return;

  var picks = Array.prototype.slice.call(block.querySelectorAll(".stories__pick"));
  var back = block.querySelector("[data-stories-back]");
  var next = block.querySelector("[data-stories-next]");
  if (picks.length < 2 || !back || !next) return;

  var quiet = window.matchMedia("(prefers-reduced-motion: reduce)");

  // Las flechas solo existen si este archivo corrió.
  block.classList.add("is-ready");

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

  /* Lo que espera después de un cambio a mano, con la barra gris. */
  var WAIT = 1000;
  var seen = !window.IntersectionObserver;   // sin observador, se da por visto
  var away = false;                          // la pestaña, escondida
  var hold = null;                           // la espera tras un cambio a mano

  function sync() {
    var on = !quiet.matches;
    block.classList.toggle("is-playing", on);
    block.classList.toggle("is-paused", !(on && seen && !away && !hold));
  }

  /* El caso nuevo estrena su animación, así que en pausa su barra queda gris;
     al acabar la espera empieza a llenarse desde cero. */
  function wait() {
    window.clearTimeout(hold);
    hold = window.setTimeout(function () { hold = null; sync(); }, WAIT);
    sync();
  }

  /* La barra se llenó: toca el siguiente. La suya empieza de cero sola, porque
     la animación solo la lleva la barra del abierto. */
  block.addEventListener("animationend", function (event) {
    if (event.animationName === "stories-fill") open(current() + 1);
  });

  /* `change` solo salta cuando el radio lo cambia una persona (pulsando una
     barra o con las flechas del teclado), nunca cuando lo marca este guion. */
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

  /* -------------------------------------------------------------- las flechas */

  /* Marcan el radio desde aquí, así que no salta `change`: la espera la
     arrancan ellas. Dan la vuelta: después del último viene el primero. */
  function go(by) {
    return function () {
      open(current() + by);
      wait();
    };
  }

  back.addEventListener("click", go(-1));
  next.addEventListener("click", go(1));
})();
