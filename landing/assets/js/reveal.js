/* La portada que se va descubriendo al bajar (octubre de 2026).

   Al entrar en pantalla:
     * los títulos de cada sección salen palabra por palabra;
     * las tarjetas (planes, preguntas) suben con un poco de retraso entre ellas;
     * los precios de los planes cuentan hasta su número.

   **Nada queda escondido sin este archivo**: el CSS solo esconde lo que va a
   aparecer cuando `<html>` lleva `js-reveal`, y esa clase la pone este script
   justo antes de empezar a mirar. Con «reducir movimiento», o sin
   IntersectionObserver, no hace nada y todo se ve quieto y completo. Los
   textos no cambian: solo se envuelven sus palabras. */
(function () {
  "use strict";

  if (!("IntersectionObserver" in window)) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var root = document.documentElement;

  /* Cada palabra en su caja, con su número para el retraso. Recorre también
     lo que el título lleva dentro (la frase destacada del inicio). */
  function splitWords(node, state) {
    Array.prototype.slice.call(node.childNodes).forEach(function (child) {
      if (child.nodeType === 3) {
        var parts = child.nodeValue.split(/(\s+)/);
        var frag = document.createDocumentFragment();
        parts.forEach(function (part) {
          if (!part) return;
          if (/^\s+$/.test(part)) {
            frag.appendChild(document.createTextNode(part));
            return;
          }
          var word = document.createElement("span");
          word.className = "word";
          word.style.setProperty("--i", state.i++);
          word.textContent = part;
          frag.appendChild(word);
        });
        child.parentNode.replaceChild(frag, child);
      } else if (child.nodeType === 1) {
        splitWords(child, state);
      }
    });
  }

  /* Contar hasta el precio. Si plans.js lo cambia a mitad (mensual o anual),
     se deja de contar: manda lo que eligió quien mira. */
  function countUp(el) {
    var target = parseInt(el.textContent.replace(/[^0-9]/g, ""), 10);
    if (!target) return;
    var start = null;
    var last = "0";
    el.textContent = last;
    function frame(now) {
      if (el.textContent !== last) return;
      if (start === null) start = now;
      var p = Math.min(1, (now - start) / 700);
      var eased = 1 - Math.pow(1 - p, 3);
      last = String(Math.round(target * eased));
      el.textContent = last;
      if (p < 1) window.requestAnimationFrame(frame);
    }
    window.requestAnimationFrame(frame);
  }

  var titles = document.querySelectorAll(".hero__title, .section__title");
  var cards = document.querySelectorAll(".plan, .faq__item, .story__side");
  var prices = document.querySelectorAll(".plan [data-price]");

  Array.prototype.forEach.call(titles, function (title) {
    title.classList.add("reveal-words");
    splitWords(title, { i: 0 });
  });
  Array.prototype.forEach.call(cards, function (card) {
    var siblings = card.parentNode ? Array.prototype.indexOf.call(card.parentNode.children, card) : 0;
    card.classList.add("reveal-rise");
    card.style.setProperty("--i", Math.max(0, siblings));
  });

  root.classList.add("js-reveal");

  var seen = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      el.classList.add("is-revealed");
      seen.unobserve(el);
      if (el.hasAttribute("data-price")) countUp(el);
      // Terminada la entrada, la tarjeta suelta sus clases: con ellas puestas,
      // `transform: none` le ganaba al hover y los planes ya no se levantaban.
      if (el.classList.contains("reveal-rise")) {
        var wait = (parseFloat(el.style.getPropertyValue("--i")) || 0) * 90 + 800;
        window.setTimeout(function () {
          el.classList.remove("reveal-rise", "is-revealed");
          el.style.removeProperty("--i");
        }, wait);
      }
    });
  }, { threshold: 0.25, rootMargin: "0px 0px -8% 0px" });

  Array.prototype.forEach.call(titles, function (el) { seen.observe(el); });
  Array.prototype.forEach.call(cards, function (el) { seen.observe(el); });
  Array.prototype.forEach.call(prices, function (el) { seen.observe(el); });

  // Al imprimir, todo a la vista.
  window.addEventListener("beforeprint", function () {
    Array.prototype.forEach.call(document.querySelectorAll(".reveal-words, .reveal-rise"),
      function (el) { el.classList.add("is-revealed"); });
  });
})();
