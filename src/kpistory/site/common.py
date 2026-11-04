"""Building blocks shared by the case pages: KPI tiles, story sections, monitoring tables."""

from __future__ import annotations

import html
from dataclasses import dataclass

from ..engine import Engine, format_threshold, format_value
from ..viz import theme


@dataclass
class Tile:
    kpi_id: str
    value: float
    context: str = ""  # e.g. "Q4 2024" or "vs 96.4% in Q3"


def tiles(engine: Engine, items: list[Tile], depth: int = 2) -> str:
    """Row of KPI cards: value, status (icon + word, never colour alone), target rule."""
    up = "../" * depth
    cards = []
    for t in items:
        k = engine.catalog[t.kpi_id]
        status = engine.status(t.kpi_id, t.value)
        cards.append(
            f'<a class="kpi-tile status-{status.replace("/", "")}" href="{up}catalog/{k.id}/">'
            f'<span class="kpi-name">{html.escape(k.name)}</span>'
            f'<span class="kpi-value">{format_value(k, t.value)}</span>'
            f'<span class="kpi-status"><span class="icon">{theme.STATUS_ICON[status]}</span> '
            f"{theme.STATUS_TEXT[status]} · target {html.escape(format_threshold(k).split(' (')[0])}</span>"
            f'<span class="kpi-context">{html.escape(t.context)}</span></a>'
        )
    return '<div class="kpi-grid">\n' + "\n".join(cards) + "\n</div>\n\n"


def source_note(manifest: dict, keys: list[str]) -> str:
    parts = []
    for key in keys:
        m = manifest[key]
        label = "real public data" if m["origin"] == "real" else "synthetic"
        parts.append(f"**{m['name']}** - {label}")
    return (
        '!!! info "Data used on this page"\n'
        f"    {' · '.join(parts)}. Details on the [data sources](../data-sources.md) page. "
        "With synthetic data the findings illustrate the method; they are not claims about a real organisation.\n\n"
    )


def question(text: str) -> str:
    return f'<p class="story-question">{html.escape(text)}</p>\n\n'


def monitoring_table(engine: Engine, rows: list[tuple[str, str, str]]) -> str:
    """rows: (kpi_id, cadence, trigger). Owner and target come from the catalog."""
    out = ["| KPI | Owner | Cadence | Target | Trigger for action |", "|---|---|---|---|---|"]
    for kpi_id, cadence, trigger in rows:
        k = engine.catalog[kpi_id]
        out.append(
            f"| [{k.name}](../catalog/{k.id}.md) | {k.owner} | {cadence} | {format_threshold(k).split(' (')[0]} | {trigger} |"
        )
    return "\n".join(out) + "\n\n"


def fmt(engine: Engine, kpi_id: str, value: float) -> str:
    return format_value(engine.catalog[kpi_id], value)


def pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}%"
