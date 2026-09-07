/* Theme switch for the account pages. No dependencies.
   The same behaviour as the landing site's nav.js, without the mobile menu. */
(function () {
  "use strict";

  // The head script already set data-theme before the first paint. Here we only
  // handle switching it, remembering the choice, and the reveal animation.

  var themeBtn = document.getElementById("theme-toggle");
  var themeMeta = document.getElementById("theme-color");
  var THEME_COLOR = { light: "#3166A7", dark: "#245285" };
  if (!themeBtn) return;

  function currentTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function labelFor(theme) {
    // The button says what it will do, not what is on.
    return theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
  }

  function paintTheme(theme) {
    document.documentElement.dataset.theme = theme;
    if (themeMeta) themeMeta.setAttribute("content", THEME_COLOR[theme]);
    themeBtn.setAttribute("aria-label", labelFor(theme));
  }

  themeBtn.setAttribute("aria-label", labelFor(currentTheme()));

  themeBtn.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", next); } catch (e) {}

    var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!document.startViewTransition || reduced) {
      paintTheme(next);
      return;
    }

    // Circular reveal growing from the button to the farthest corner.
    var r = themeBtn.getBoundingClientRect();
    var x = r.left + r.width / 2;
    var y = r.top + r.height / 2;
    var radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    var transition = document.startViewTransition(function () { paintTheme(next); });
    transition.ready.then(function () {
      document.documentElement.animate(
        { clipPath: ["circle(0px at " + x + "px " + y + "px)",
                     "circle(" + radius + "px at " + x + "px " + y + "px)"] },
        { duration: 450, easing: "cubic-bezier(.2,.7,.2,1)",
          pseudoElement: "::view-transition-new(root)" }
      );
    }).catch(function () { /* the theme already changed; the animation is a bonus */ });
  });
})();
