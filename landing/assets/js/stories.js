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

   **Si alguien pulsa una barra o una flecha, deja de pasar solo** para el
   resto de la visita, como en «¿Sigues enviando…?», y la barra del abierto
   queda llena: quien elige un caso lo está mirando a su ritmo.

   Mientras nadie lo toque, se detiene con el ratón encima o con el foco dentro
   y vuelve a andar al quitarlo, no corre fuera de la pantalla ni con la pestaña
   escondida, y con «reducir movimiento» puesto no existe. Las flechas, sí.

   Estas pausas son las mismas que las de trouble.js y están escritas otra vez
   a propósito: cada archivo se lee por su cuenta y tocar uno no puede romper
   el otro. */
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

  var seen = !window.IntersectionObserver;   // sin observador, se da por visto
  var over = false;                          // el ratón o el foco, dentro
  var away = false;                          // la pestaña, escondida
  var mine = false;                          // alguien lo movió a mano

  function sync() {
    var on = !mine && !quiet.matches;
    block.classList.toggle("is-playing", on);
    block.classList.toggle("is-paused", !(on && seen && !over && !away));
  }

  /* La barra se llenó: toca el siguiente. La suya empieza de cero sola, porque
     la animación solo la lleva la barra del abierto. */
  block.addEventListener("animationend", function (event) {
    if (event.animationName === "stories-fill") open(current() + 1);
  });

  function inside(yes) {
    return function () { over = yes; sync(); };
  }

  block.addEventListener("pointerenter", inside(true));
  block.addEventListener("pointerleave", inside(false));
  block.addEventListener("focusin", inside(true));
  block.addEventListener("focusout", inside(false));

  /* `change` solo salta cuando el radio lo cambia una persona (pulsando una
     barra o con las flechas del teclado), nunca cuando lo marca este guion. */
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

  /* -------------------------------------------------------------- las flechas */

  /* Marcan el radio desde aquí, así que no salta `change`: el cambio a mano lo
     apuntan ellas. Dan la vuelta: después del último viene el primero. */
  function go(by) {
    return function () {
      mine = true;
      open(current() + by);
      sync();
    };
  }

  back.addEventListener("click", go(-1));
  next.addEventListener("click", go(1));
})();
