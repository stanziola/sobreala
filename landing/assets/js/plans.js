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
        entry.target.classList.add("is-in");
        watcher.unobserve(entry.target);
      });
    }, { threshold: 0.2 });
    cards.forEach(function (card) { watcher.observe(card); });
  }

  /* -------------------------------------------------------- el confeti */

  /* Unos papelitos cayendo sobre el interruptor al elegir el año. Se dibuja en
     su propio canvas, dura dos segundos y se borra solo: no deja nada corriendo
     ni escucha nada. */
  var COLORS = ["#2F6FB3", "#31A9E8", "#0B3B5C", "#E0F2FE"];
  var PIECES = 70;
  var LIFE_MS = 2000;

  function confetti() {
    if (!confettiCanvas || quiet.matches) return;
    // El lienzo es más grande que el interruptor, para que los papelitos se
    // vean caer; el punto de salida es el centro del botón, no el del lienzo.
    var box = confettiCanvas.getBoundingClientRect();
    var from = (root.querySelector(".cycle__switch") || root).getBoundingClientRect();
    var originX = from.left + from.width / 2 - box.left;
    var originY = from.top + from.height / 2 - box.top;
    var scale = window.devicePixelRatio || 1;
    confettiCanvas.width = box.width * scale;
    confettiCanvas.height = box.height * scale;
    var pen = confettiCanvas.getContext("2d");
    if (!pen) return;
    pen.setTransform(scale, 0, 0, scale, 0, 0);

    var bits = [];
    for (var i = 0; i < PIECES; i++) {
      var angle = (-90 + (Math.random() - 0.5) * 70) * Math.PI / 180;
      var speed = 3 + Math.random() * 4;
      bits.push({
        x: originX, y: originY,
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
        size: 3 + Math.random() * 3,
        color: COLORS[i % COLORS.length],
        spin: (Math.random() - 0.5) * 0.3, turn: Math.random() * Math.PI,
      });
    }

    var started = 0;
    function draw(now) {
      if (!started) started = now;
      var life = (now - started) / LIFE_MS;
      pen.clearRect(0, 0, box.width, box.height);
      if (life >= 1) return;
      pen.globalAlpha = 1 - life;
      bits.forEach(function (bit) {
        bit.x += bit.vx;
        bit.y += bit.vy;
        bit.vy += 0.18;          // la gravedad
        bit.vx *= 0.99;
        bit.turn += bit.spin;
        pen.save();
        pen.translate(bit.x, bit.y);
        pen.rotate(bit.turn);
        pen.fillStyle = bit.color;
        pen.fillRect(-bit.size / 2, -bit.size / 2, bit.size, bit.size * 1.6);
        pen.restore();
      });
      requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
  }
})();
