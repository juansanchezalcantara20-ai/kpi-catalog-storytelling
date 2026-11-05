// Accessible tooltips for KPI cards and traffic lights (site and dashboard).
// Trigger: any element with data-tip and aria-describedby="<tooltip id>". Opens on hover, keyboard
// focus or tap; closes with Esc or on leave. On touch screens the first tap opens the tooltip and a
// second tap on the same card follows its link (or selects it on the dashboard).
// Placement: below the trigger, else above, else beside it, else clamped - always inside the viewport.
(function () {
  let open = null, openTrigger = null, lastPointer = "mouse", allowTap = false;
  function hide() { if (open) { open.hidden = true; open = null; openTrigger = null; } }
  function place(tip, trigger) {
    tip.hidden = false;
    tip.style.left = "0px"; tip.style.top = "0px";
    const r = trigger.getBoundingClientRect(), t = tip.getBoundingClientRect();
    const vw = document.documentElement.clientWidth, vh = window.innerHeight, m = 8, g = 6;
    const clampX = x => Math.min(Math.max(m, x), vw - t.width - m);
    const clampY = y => Math.min(Math.max(m, y), vh - t.height - m);
    let left, top;
    if (r.bottom + g + t.height <= vh - m) { left = clampX(r.left); top = r.bottom + g; }
    else if (r.top - g - t.height >= m) { left = clampX(r.left); top = r.top - g - t.height; }
    else if (r.right + g + t.width <= vw - m) { left = r.right + g; top = clampY(r.top); }
    else if (r.left - g - t.width >= m) { left = r.left - g - t.width; top = clampY(r.top); }
    else { left = clampX(r.left); top = clampY(r.bottom + g); }
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  function show(trigger) {
    const id = trigger.getAttribute("aria-describedby");
    const tip = id && document.getElementById(id);
    if (!tip) return;
    if (open && open !== tip) hide();
    open = tip; openTrigger = trigger;
    place(tip, trigger);
  }
  function triggerOf(el) { return el && el.closest ? el.closest("[data-tip]") : null; }
  document.addEventListener("pointerdown", e => {
    lastPointer = e.pointerType;
    if (e.pointerType !== "touch") return;
    const t = triggerOf(e.target);
    if (!t) { hide(); return; }
    allowTap = open !== null && openTrigger === t;  // second tap on the same trigger
    if (!allowTap) show(t);
  }, true);
  document.addEventListener("click", e => {
    if (lastPointer === "touch" && triggerOf(e.target) && !allowTap) { e.preventDefault(); }
  }, true);
  document.addEventListener("mouseover", e => { if (lastPointer === "touch") return; const t = triggerOf(e.target); if (t) show(t); });
  document.addEventListener("mouseout", e => {
    if (lastPointer === "touch") return;
    const t = triggerOf(e.target);
    if (t && !t.contains(e.relatedTarget)) { const inner = triggerOf(e.relatedTarget); inner ? show(inner) : hide(); }
  });
  document.addEventListener("focusin", e => { const t = triggerOf(e.target); if (t) show(t); });
  document.addEventListener("focusout", () => { if (lastPointer !== "touch") hide(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", () => { if (open && openTrigger) place(open, openTrigger); }, {passive: true});
  window.kpiTooltipHide = hide;
})();
