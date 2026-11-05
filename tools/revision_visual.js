// Visual review of the built site (run after `make all`):
//   NODE_PATH=$(npm root -g) node tools/revision_visual.js
// For the home page, the management summary, one rubro, one case with an observed result and the
// dashboard filtered by rubro and tema (#/rubro/mineria/tema/mantenimiento), on desktop (1280 px) and
// phone (390 px): takes a screenshot into docs/capturas/, checks there is no horizontal scroll and
// that a KPI tooltip opens fully inside the viewport. Exits with code 1 if a check fails.
const { chromium } = require("playwright");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SITE = "file://" + path.join(ROOT, "site");
const OUT = path.join(ROOT, "docs", "capturas");
const PAGES = [
  ["portada", "/index.html", null],
  ["portada-matriz", "/index.html", null],
  ["resumen", "/resumen/index.html", null],
  ["rubro", "/rubros/energia/index.html", "a.kpi-tile"],
  ["caso-observado", "/cases/energia/index.html", "a.kpi-tile"],
  ["caso-resultado", "/cases/energia/index.html#resultado", null],
  ["tablero", "/dashboard/index.html", "button.card"],
  ["tablero-filtrado", "/dashboard/index.html#/rubro/mineria/tema/mantenimiento", null],
];
const DEVICES = [
  ["escritorio", { viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 }],
  ["celular", { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }],
];

(async () => {
  const browser = await chromium.launch();
  const failures = [];
  for (const [device, opts] of DEVICES) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    page.on("pageerror", (e) => failures.push(`${device}: error de JavaScript: ${e.message}`));
    for (const [name, url, tipSelector] of PAGES) {
      await page.goto(SITE + url);
      await page.waitForTimeout(2500);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 1) failures.push(`${device} ${name}: scroll horizontal de ${overflow}px`);
      if (name === "tablero-filtrado") {
        const r = await page.evaluate(() => {
          const shown = document.querySelectorAll("#tarjetas button.card").length;
          const want = DATA.kpis.filter((k) => k.rubros.includes("mineria") && k.tema === "mantenimiento").length;
          return { shown, want, rubro: document.getElementById("f-rubro").value, tema: document.getElementById("f-tema").value, hash: location.hash };
        });
        if (r.shown !== r.want || r.rubro !== "mineria" || r.tema !== "mantenimiento")
          failures.push(`${device} ${name}: el filtro no se aplicó (${JSON.stringify(r)})`);
        await page.selectOption("#f-tema", "all");
        const h = await page.evaluate(() => location.hash);
        if (!h.startsWith("#/rubro/mineria") || h.includes("tema")) failures.push(`${device} ${name}: la dirección no se actualizó (${h})`);
        await page.selectOption("#f-tema", "mantenimiento");
        await page.mouse.move(1, 1);
        await page.keyboard.press("Escape");
        await page.evaluate(() => document.querySelector(".toolbar").scrollIntoView());
        await page.waitForTimeout(800);
      }
      if (name === "portada-matriz") {
        await page.evaluate(() => document.querySelector(".matriz").scrollIntoView());
        await page.waitForTimeout(300);
      }
      if (name === "caso-resultado") {
        await page.evaluate(() => document.getElementById("resultado").scrollIntoView());
        await page.waitForTimeout(300);
      }
      await page.screenshot({ path: path.join(OUT, `${device}-${name}.png`), fullPage: false });
      if (tipSelector) {
        const el = await page.$(tipSelector);
        await el.scrollIntoViewIfNeeded();
        await page.waitForTimeout(200);
        if (opts.hasTouch) await el.tap({ position: { x: 20, y: 20 } });
        else await el.hover({ position: { x: 20, y: 20 } });
        await page.waitForTimeout(300);
        const box = await page.evaluate(() => {
          const t = [...document.querySelectorAll('[role="tooltip"]')].find((x) => !x.hidden);
          if (!t) return null;
          const r = t.getBoundingClientRect();
          return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, w: innerWidth, h: innerHeight };
        });
        if (!box) failures.push(`${device} ${name}: el tooltip no se abrió`);
        else if (box.left < 0 || box.top < 0 || box.right > box.w || box.bottom > box.h)
          failures.push(`${device} ${name}: el tooltip se corta (${JSON.stringify(box)})`);
        await page.screenshot({ path: path.join(OUT, `${device}-${name}-tooltip.png`), fullPage: false });
        await page.keyboard.press("Escape");
      }
    }
    await ctx.close();
  }
  await browser.close();
  if (failures.length) {
    console.log("Revisión visual: FALLA\n - " + failures.join("\n - "));
    process.exit(1);
  }
  console.log("Revisión visual: OK (sin scroll horizontal, tooltips completos). Capturas en docs/capturas/");
})();
