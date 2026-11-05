// Visual review of the built site (run after `make all`):
//   NODE_PATH=$(npm root -g) node tools/revision_visual.js
// For the home page, the management summary, one case and the dashboard, on desktop (1280 px) and
// phone (390 px): takes a screenshot into docs/capturas/, checks there is no horizontal scroll and
// that a KPI tooltip opens fully inside the viewport. Exits with code 1 if a check fails.
const { chromium } = require("playwright");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SITE = "file://" + path.join(ROOT, "site");
const OUT = path.join(ROOT, "docs", "capturas");
const PAGES = [
  ["portada", "/index.html", null],
  ["resumen", "/resumen/index.html", null],
  ["caso", "/cases/service/index.html", "a.kpi-tile"],
  ["tablero", "/dashboard/index.html", "button.card"],
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
