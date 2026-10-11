/* El carrusel de Features, que en la página se llama «Funciones». Sin
   dependencias, como nav.js.

   La sección funciona entera sin este archivo: lo que abre cada dibujo son
   botones de radio y las barras de debajo son sus etiquetas, así que se pulsa
   con el ratón, se mueve con las flechas del teclado y en el teléfono se ven
   las nueve con su texto. Lo de aquí son dos añadidos, y ninguno existe sin
   este archivo: las flechas de anterior y siguiente, y el paso automático.

   **El reloj es la barra de la función abierta**, una animación de CSS que dura
   --tour-every (site.css), como en «Haz crecer tu negocio»: este archivo espera
   a que se llene (`animationend`) y abre la siguiente. Pone tres clases en el
   bloque: `is-ready`, porque corrió (y con ella se ven las flechas);
   `is-playing`, con el paso automático encendido; e `is-paused`, cuando se
   detiene un momento (la barra se queda donde iba). En el teléfono las barras
   no se dibujan, así que tampoco pasa sola: ahí se ven todas a la vez.

   **Si alguien pulsa una barra o una flecha, espera un segundo** con la barra
   de la nueva gris, y después el azul empieza a llenarla otra vez. Otro cambio
   antes de tiempo vuelve a empezar la espera. Hasta octubre de 2026 pasaba
   cada cuatro segundos con un `setInterval`, sin barra, y el ratón encima o el
   foco dentro lo pausaban.

   No corre fuera de la pantalla ni con la pestaña escondida, y con «reducir
   movimiento» puesto no existe. Las flechas, sí.

   Estas reglas son las mismas que las de stories.js y trouble.js, y están
   escritas otra vez a propósito: cada archivo se lee por su cuenta y tocar uno
   no puede romper los otros. */
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
  var seen = !window.IntersectionObserver;   // sin observador, se da por vista
  var away = false;                          // la pestaña, escondida
  var hold = null;                           // la espera tras un cambio a mano

  function sync() {
    var on = !quiet.matches;
    tour.classList.toggle("is-playing", on);
    tour.classList.toggle("is-paused", !(on && seen && !away && !hold));
  }

  /* La función nueva estrena su animación, así que en pausa su barra queda
     gris; al acabar la espera el azul empieza a llenarla desde cero. */
  function wait() {
    window.clearTimeout(hold);
    hold = window.setTimeout(function () { hold = null; sync(); }, WAIT);
    sync();
  }

  /* La barra se llenó: toca la siguiente. La suya empieza de cero sola, porque
     la animación solo la lleva la barra de la abierta. */
  tour.addEventListener("animationend", function (event) {
    if (event.animationName === "tour-fill") open(current() + 1);
  });

  /* `change` solo salta cuando el radio lo cambia una persona (pulsando un
     dibujo o una barra, o con las flechas del teclado), nunca cuando lo marca
     este guion. */
  picks.forEach(function (pick) {
    pick.addEventListener("change", wait);
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

  /* Marcan el radio desde aquí, así que no salta `change`: la espera la
     arrancan ellas. Dan la vuelta: después de la última viene la primera. */
  function go(by) {
    return function () {
      open(current() + by);
      wait();
    };
  }

  back.addEventListener("click", go(-1));
  next.addEventListener("click", go(1));
})();
