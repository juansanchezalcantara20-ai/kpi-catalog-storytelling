// "¿Y si…?" simulator: move the main KPI with a slider and edit the cost assumptions; the monthly
// saving is recomputed live with the same linear model as the Python engine (valor.py):
//   cost per month = base x gap(value, target) x cost per unit, gap never negative.
(function () {
  const fmtNum = (x, d = 0) => x.toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}).replace(/,/g, " ");
  const soles = x => "S/ " + fmtNum(Math.round(x));
  const gap = (v, c) => c.direccion === "lower_is_better" ? Math.max(0, v - c.meta) : Math.max(0, c.meta - v);
  const show = (v, c) => c.unidad_pct ? fmtNum(v * 100, 1) + " %" : fmtNum(v, 1);

  function build(el) {
    const data = JSON.parse(el.querySelector("script[type='application/json']").textContent);
    const comps = data.componentes, main = comps[0];
    const lo = main.direccion === "lower_is_better" ? Math.min(main.meta, main.valor) * 0.5 : Math.min(main.valor, main.meta) * 0.9;
    const hi = main.direccion === "lower_is_better" ? Math.max(main.valor, main.meta) : Math.min(main.unidad_pct ? 1 : main.meta * 1.2, Math.max(main.valor, main.meta) * 1.05);
    const step = (hi - lo) / 200;
    const uid = "sim-" + data.caso;
    let html = `<p class="sim-titulo"><b>¿Y si…?</b> Mueva el valor de «${main.nombre}» y vea cuánto se ahorra al mes.</p>
      <label for="${uid}-v">Nuevo valor de «${main.nombre}»: <span id="${uid}-vt"></span> (hoy ${show(main.valor, main)}, meta ${show(main.meta, main)})</label>
      <input type="range" id="${uid}-v" min="${lo}" max="${hi}" step="${step}" value="${main.meta}">
      <div class="fila">`;
    comps.forEach((c, i) => {
      html += `<label for="${uid}-c${i}">Costo en S/ por unidad<br><small>${c.unidad}</small><br><input type="number" id="${uid}-c${i}" min="0" step="any" value="${c.costo_unitario}"></label>`;
      if (c.horas_unitarias > 0) html += `<label for="${uid}-h${i}">Horas por unidad<br><small>${c.unidad}</small><br><input type="number" id="${uid}-h${i}" min="0" step="any" value="${c.horas_unitarias}"></label>`;
    });
    html += `</div><p class="resultado" id="${uid}-r" aria-live="polite"></p><p class="aviso-supuestos">Supuestos ilustrativos; cámbielos con los de su empresa. El método es el mismo con cualquier número.</p>`;
    el.insertAdjacentHTML("beforeend", html);
    const slider = el.querySelector(`#${uid}-v`);
    function update() {
      const v = parseFloat(slider.value);
      let antes = 0, despues = 0, hAntes = 0, hDespues = 0;
      comps.forEach((c, i) => {
        const cost = parseFloat(el.querySelector(`#${uid}-c${i}`).value) || 0;
        const hEl = el.querySelector(`#${uid}-h${i}`), hrs = hEl ? (parseFloat(hEl.value) || 0) : 0;
        const now = c.base * gap(c.valor, c) , nuevo = c.base * gap(i === 0 ? v : c.valor, c);
        antes += now * cost; despues += nuevo * cost; hAntes += now * hrs; hDespues += nuevo * hrs;
      });
      el.querySelector(`#${uid}-vt`).textContent = show(v, main);
      const ahorro = antes - despues, horas = hAntes - hDespues;
      el.querySelector(`#${uid}-r`).textContent = ahorro >= 0
        ? `Si «${main.nombre}» pasa de ${show(main.valor, main)} a ${show(v, main)}: ahorro de ${soles(ahorro)} al mes (${soles(ahorro * 12)} al año) y ${fmtNum(horas)} horas de trabajo al mes.`
        : `Con ${show(v, main)} el costo sube ${soles(-ahorro)} al mes.`;
    }
    el.addEventListener("input", update);
    update();
  }
  function init() { document.querySelectorAll(".simulador[data-sim]").forEach(el => { if (!el.dataset.listo) { el.dataset.listo = "1"; build(el); } }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
