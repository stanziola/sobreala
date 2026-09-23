/* Los cuatro puntos de «El problema», en la portada. Sin dependencias, como
   nav.js.

   El bloque funciona entero sin este archivo: lo que abre cada punto son
   botones de radio, así que se pulsa con el ratón, se mueve con las flechas del
   teclado y se ve igual de bien. Lo de aquí es un añadido: pasar al siguiente
   solo, y encender la cuenta atrás que lo anuncia.

   El paso se detiene con el ratón encima o con el foco dentro y vuelve a andar
   al quitarlo, no corre fuera de la pantalla ni con la pestaña escondida, y con
   «reducir movimiento» puesto no existe: quien lo pide no quiere que la página
   se mueva mientras lee.

   Estas reglas son las mismas que las del carrusel de capturas y están escritas
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

  // La cuenta atrás solo se dibuja si este archivo corrió.
  block.classList.add("is-ready");

  /* Cuánto dura cada punto lo dice el CSS, que es quien también anima la barra:
     así el número no queda escrito en dos sitios que se puedan separar. */
  function every() {
    var raw = window.getComputedStyle(block).getPropertyValue("--trouble-every").trim();
    var many = parseFloat(raw);
    if (!many) return 6000;
    return /ms$/.test(raw) ? many : many * 1000;
  }

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

  var timer = null;
  var seen = !window.IntersectionObserver;   // sin observador, se da por visto
  var over = false;                          // el ratón o el foco, dentro
  var away = false;                          // la pestaña, escondida

  function sync() {
    var run = seen && !over && !away && !quiet.matches;
    if (run && !timer) {
      timer = window.setInterval(function () { open(current() + 1); }, every());
    } else if (!run && timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  /* Elegir uno a mano **no lo apaga**: solo vuelve a empezar la cuenta, para
     que el que se acaba de pulsar no se cambie medio segundo después. */
  function restart() {
    if (!timer) return;
    window.clearInterval(timer);
    timer = null;
    sync();
  }

  function inside(yes) {
    return function () { over = yes; sync(); };
  }

  block.addEventListener("pointerenter", inside(true));
  block.addEventListener("pointerleave", inside(false));
  block.addEventListener("focusin", inside(true));
  block.addEventListener("focusout", inside(false));
  picks.forEach(function (pick) {
    pick.addEventListener("change", restart);
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
