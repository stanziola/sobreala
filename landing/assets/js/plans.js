/* Las tarjetas de /planes: mensual o anual, el precio que cambia, la entrada y
   el confeti. Sin dependencias, como nav.js.

   La página nace en mensual y con todo dibujado, así que sin este archivo se
   siguen viendo los tres planes, sus precios y sus botones. Lo de aquí es un
   añadido, nunca el único camino.

   Quien tenga «reducir movimiento» puesto en su sistema cambia de ciclo igual:
   el precio salta de golpe, sin contador ni confeti. */
(function () {
  "use strict";

  var root = document.querySelector("[data-cycle]");
  var cards = Array.prototype.slice.call(document.querySelectorAll("[data-plan]"));
  if (!root || !cards.length) return;

  var quiet = window.matchMedia("(prefers-reduced-motion: reduce)");
  var options = Array.prototype.slice.call(root.querySelectorAll("[data-cycle-set]"));
  var confettiCanvas = root.querySelector("[data-confetti]");
  var save = root.querySelector(".cycle__save");
  var yearly = false;

  // El interruptor solo existe si este archivo corrió: un botón que no hace
  // nada es peor que no tenerlo.
  root.classList.add("is-ready");

  /* ------------------------------------------------- el número que cambia */

  /* Medio segundo, saliendo despacio al final: es lo que hace que el ojo
     siga la cifra en vez de ver dos números distintos. */
  var COUNT_MS = 500;

  function easeOut(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function countTo(el, to) {
    var from = parseInt(el.textContent, 10);
    if (isNaN(from) || from === to || quiet.matches) {
      el.textContent = String(to);
      return;
    }
    if (el._stop) cancelAnimationFrame(el._stop);
    var started = 0;
    function step(now) {
      if (!started) started = now;
      var share = Math.min(1, (now - started) / COUNT_MS);
      el.textContent = String(Math.round(from + (to - from) * easeOut(share)));
      if (share < 1) el._stop = requestAnimationFrame(step);
    }
    el._stop = requestAnimationFrame(step);
  }

  /* --------------------------------------------------------- el ciclo */

  function paint() {
    cards.forEach(function (card) {
      var price = card.querySelector("[data-price]");
      var note = card.querySelector("[data-note]");
      var to = parseInt(card.getAttribute(yearly ? "data-yearly-monthly" : "data-monthly"), 10);
      if (price && !isNaN(to)) countTo(price, to);
      if (note) {
        note.textContent = card.getAttribute(yearly ? "data-note-yearly" : "data-note-monthly");
      }
      // El botón lleva el ciclo al panel, que resalta el que se eligió aquí.
      // nav.js sigue mandando en su texto; esto solo le toca la dirección.
      var buy = card.querySelector("[data-buy]");
      if (buy) {
        buy.setAttribute("href", buy.getAttribute("data-buy") + (yearly ? "?ciclo=anual" : ""));
      }
    });
    options.forEach(function (one) {
      var on = (one.getAttribute("data-cycle-set") === "yearly") === yearly;
      one.classList.toggle("is-on", on);
      one.setAttribute("aria-pressed", on ? "true" : "false");
    });
    // El descuento es del año: con el mes puesto se queda apagado.
    if (save) save.classList.toggle("is-on", yearly);
    // nav.js decide qué dice cada botón según el plan que se tiene y el ciclo.
    document.dispatchEvent(new CustomEvent("sa:cycle", { detail: { yearly: yearly } }));
  }

  options.forEach(function (one) {
    one.addEventListener("click", function () {
      var wanted = one.getAttribute("data-cycle-set") === "yearly";
      if (wanted === yearly) return;
      yearly = wanted;
      paint();
      if (yearly) confetti();
    });
  });

  /* ------------------------------------------------------- la entrada */

  /* Las tarjetas entran de abajo cuando se llega a ellas, una detrás de otra.
     Sin IntersectionObserver —o con el movimiento apagado— se quedan puestas,
     que es como nacen en el CSS. */
  if (!quiet.matches && "IntersectionObserver" in window) {
    cards.forEach(function (card, index) {
      card.classList.add("plan--enter");
      card.style.transitionDelay = (index * 90) + "ms";
    });
    var watcher = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var card = entry.target;
        card.classList.add("is-in");
        watcher.unobserve(card);
        // Al terminar de entrar, la tarjeta se queda como nació en el CSS: sin
        // las clases de la entrada y sin su retraso, que si no se queda puesto
        // y el hover tardaría en arrancar.
        window.setTimeout(function () {
          card.classList.remove("plan--enter", "is-in");
          card.style.transitionDelay = "";
        }, 900 + (parseInt(card.style.transitionDelay, 10) || 0));
      });
    }, { threshold: 0.2 });
    cards.forEach(function (card) { watcher.observe(card); });
  }

  /* -------------------------------------------------------- el confeti */

  /* Unos papelitos que salen del interruptor al elegir el año y caen hasta
     abajo de la pantalla. Se dibujan en su propio canvas, que ocupa la ventana
     entera y no recibe clics, y se borra solo cuando el último sale de vista:
     no deja nada corriendo ni escucha nada. */
  var COLORS = ["#2F6FB3", "#31A9E8", "#0B3B5C", "#E0F2FE"];
  var PIECES = 90;
  var MAX_MS = 9000;        // por si alguno se queda dando vueltas

  function confetti() {
    if (!confettiCanvas || quiet.matches) return;
    var wide = confettiCanvas.clientWidth;
    var tall = confettiCanvas.clientHeight;
    // El punto de salida es el centro del interruptor, en coordenadas de la
    // ventana: el canvas va fijo, así que son las mismas.
    var from = (root.querySelector(".cycle__switch") || root).getBoundingClientRect();
    var originX = from.left + from.width / 2;
    var originY = from.top + from.height / 2;
    var scale = window.devicePixelRatio || 1;
    confettiCanvas.width = wide * scale;
    confettiCanvas.height = tall * scale;
    var pen = confettiCanvas.getContext("2d");
    if (!pen) return;
    pen.setTransform(scale, 0, 0, scale, 0, 0);

    var bits = [];
    for (var i = 0; i < PIECES; i++) {
      var angle = (-90 + (Math.random() - 0.5) * 90) * Math.PI / 180;
      var speed = 3 + Math.random() * 4;
      bits.push({
        x: originX, y: originY,
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
        size: 4 + Math.random() * 4,
        color: COLORS[i % COLORS.length],
        spin: (Math.random() - 0.5) * 0.14, turn: Math.random() * Math.PI,
        // Cada uno se mece a su aire mientras baja, como un papel de verdad.
        sway: 0.4 + Math.random() * 0.8, phase: Math.random() * Math.PI * 2,
      });
    }

    var started = 0;
    function draw(now) {
      if (!started) started = now;
      var life = now - started;
      pen.clearRect(0, 0, wide, tall);
      var alive = 0;
      bits.forEach(function (bit) {
        // La mitad de gravedad que antes y un tope de caída: bajan despacio y
        // se ven llegar al final de la pantalla.
        bit.vy = Math.min(bit.vy + 0.055, 2.6);
        bit.vx *= 0.995;
        bit.x += bit.vx + Math.sin((life / 600) + bit.phase) * bit.sway * 0.5;
        bit.y += bit.vy;
        bit.turn += bit.spin;
        if (bit.y - bit.size > tall) return;
        alive++;
        pen.save();
        pen.translate(bit.x, bit.y);
        pen.rotate(bit.turn);
        pen.fillStyle = bit.color;
        pen.fillRect(-bit.size / 2, -bit.size / 2, bit.size, bit.size * 1.6);
        pen.restore();
      });
      if (!alive || life > MAX_MS) {
        pen.clearRect(0, 0, wide, tall);
        return;
      }
      requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
  }
})();
