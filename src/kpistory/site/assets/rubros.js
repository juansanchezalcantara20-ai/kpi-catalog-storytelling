// «Resumen para gerencia»: el selector de rubro muestra solo las alertas de ese rubro.
(function () {
  function init() {
    var sel = document.getElementById("sel-rubro");
    if (!sel) return;
    var show = function () {
      document.querySelectorAll(".alertas-rubro").forEach(function (s) { s.hidden = s.dataset.rubro !== sel.value; });
    };
    sel.addEventListener("change", show);
    show();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
