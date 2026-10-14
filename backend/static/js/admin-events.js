/* Eventos, en administración: pedir lo nuevo cada pocos segundos y ponerlo
   arriba, sin recargar.

   El servidor devuelve las filas ya armadas (la misma plantilla que la página)
   y la hora de la más nueva. Pide con un margen hacia atrás, porque un aviso de
   Amazon puede llegar un rato después de la hora que trae, así que aquí se
   descarta lo que ya está por su `data-key`. Con la pestaña oculta no pide
   nada. Sin este archivo la página funciona igual, recargando. */
(function () {
  "use strict";

  var body = document.querySelector("tbody[data-feed]");
  if (!body || !window.fetch) { return; }

  var url = body.getAttribute("data-feed");
  var newest = body.getAttribute("data-newest");
  var empty = document.querySelector("[data-feed-empty]");
  var EVERY = 5000;   // cada cuánto se pide lo nuevo
  var MAX = 300;      // cuántas filas se guardan en pantalla
  var busy = false;

  function tick() {
    if (busy || document.visibilityState !== "visible") { return; }
    busy = true;
    var sep = url.indexOf("?") === -1 ? "?" : "&";
    fetch(url + sep + "after=" + encodeURIComponent(newest), {
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    })
      .then(function (answer) {
        if (!answer.ok) { throw new Error(String(answer.status)); }
        return answer.json();
      })
      .then(function (data) {
        newest = data.newest || newest;
        var holder = document.createElement("tbody");
        holder.innerHTML = data.html;
        var fresh = holder.querySelectorAll("tr[data-key]");
        // De la más vieja a la más nueva, para que la más nueva quede arriba.
        for (var i = fresh.length - 1; i >= 0; i--) {
          var key = fresh[i].getAttribute("data-key");
          if (body.querySelector('tr[data-key="' + key + '"]')) { continue; }
          fresh[i].classList.add("is-new");
          body.insertBefore(fresh[i], body.firstChild);
        }
        while (body.rows.length > MAX) { body.deleteRow(body.rows.length - 1); }
        if (empty) { empty.hidden = body.rows.length > 0; }
      })
      .catch(function () { /* se vuelve a intentar en la próxima vuelta */ })
      .then(function () { busy = false; });
  }

  window.setInterval(tick, EVERY);
  document.addEventListener("visibilitychange", tick);
})();
