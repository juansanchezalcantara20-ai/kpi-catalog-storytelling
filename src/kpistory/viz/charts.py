"""Chart helpers. Each returns a Plotly figure that already follows the house rules.

Percentages are passed as fractions (0.89) and drawn as "89 %" (value x 100 with a
" %" suffix), because Plotly's own percent format has no space before the sign.
"""

from __future__ import annotations

import html
import math
from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go

from . import theme
from .theme import CONTEXT, HIGHLIGHT, INK, INK_2, title

CONFIG = {"displayModeBar": False, "responsive": True, "locale": "es"}
_counter = {"n": 0}


def scale(values: Sequence, pct: bool) -> list:
    return [None if v is None or pd.isna(v) else (v * 100 if pct else v) for v in values]


def pct_axis(fig: go.Figure, axis: str = "y", decimals: int = 0) -> None:
    upd = dict(ticksuffix=" %", tickformat=f".{decimals}f")
    (fig.update_yaxes if axis == "y" else fig.update_xaxes)(**upd)


def hover(pct: bool, decimals: int = 1, suffix: str = "", var: str = "y") -> str:
    return f"%{{{var}:.{decimals}f}}" + (" %" if pct else suffix)


def to_html(
    fig: go.Figure, height: int = 400, table: pd.DataFrame | None = None, caption: str = ""
) -> str:
    """Figure -> HTML snippet for a Markdown page, followed by an optional data table."""
    _counter["n"] += 1
    title_text = fig.layout.title.text or ""
    lines = title_text.count("<br>")
    fig.update_layout(
        height=height + 20 * lines, autosize=True, margin=dict(t=60 + 20 * lines + 16)
    )
    div = fig.to_html(
        full_html=False, include_plotlyjs=False, config=CONFIG, div_id=f"grafico-{_counter['n']}"
    )
    out = f'<div class="chart" markdown="0">\n{div}\n</div>\n'
    if caption:
        out += f'<p class="chart-caption">{html.escape(caption)}</p>\n'
    if table is None:
        table = table_from_figure(fig)
    if table is not None and not table.empty:
        out += data_table(table)
    return out + "\n"


def data_table(df: pd.DataFrame, summary: str = "Ver los datos del gráfico") -> str:
    body = df.to_html(index=False, border=0, classes="data-table", na_rep="–", escape=True)
    return f"<details class='data' markdown='0'><summary>{summary}</summary>\n{body}\n</details>\n"


def add_target(
    fig: go.Figure, value: float, label: str, axis: str = "y", pct: bool = False
) -> None:
    """Thin solid reference line with a direct label (no legend entry)."""
    v = value * 100 if pct else value
    if axis == "y":
        fig.add_hline(y=v, line=dict(color=INK_2, width=1), layer="below",
                      annotation=dict(text=label, font=dict(color=INK_2, size=12), xanchor="left", x=0),
                      annotation_position="top left")  # fmt: skip
    else:
        fig.add_vline(x=v, line=dict(color=INK_2, width=1), layer="below",
                      annotation=dict(text=label, font=dict(color=INK_2, size=12)), annotation_position="top")  # fmt: skip


def add_band(fig: go.Figure, low: float, high: float, axis: str = "y", pct: bool = False) -> None:
    """Shaded green band for KPIs that must stay inside a range."""
    lo, hi = (low * 100, high * 100) if pct else (low, high)
    if axis == "y":
        fig.add_hrect(y0=lo, y1=hi, fillcolor=theme.BAND_FILL, line_width=0, layer="below")
    else:
        fig.add_vrect(x0=lo, x1=hi, fillcolor=theme.BAND_FILL, line_width=0, layer="below")


def annotate(fig: go.Figure, x, y, text: str, ax: int = 0, ay: int = -40) -> None:
    fig.add_annotation(x=x, y=y, text=text, showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=INK_2,
                       ax=ax, ay=ay, font=dict(color=INK, size=12), align="left",
                       bgcolor="rgba(252,252,251,0.85)")  # fmt: skip


def line(
    x: Sequence,
    y: Sequence,
    conclusion: str,
    subtitle: str,
    name: str = "",
    pct: bool = False,
    suffix: str = "",
    decimals: int = 1,
    context: dict[str, tuple[Sequence, Sequence]] | None = None,
) -> go.Figure:
    """One highlighted line; optional context lines in grey."""
    fig = go.Figure()
    for cname, (cx, cy) in (context or {}).items():
        fig.add_trace(go.Scatter(x=list(cx), y=scale(cy, pct), name=cname, mode="lines",
                                 line=dict(color=CONTEXT, width=1.5),
                                 hovertemplate=f"{cname}: {hover(pct, decimals, suffix)}<extra></extra>"))  # fmt: skip
    fig.add_trace(go.Scatter(x=list(x), y=scale(y, pct), name=name or "valor", mode="lines+markers",
                             line=dict(color=HIGHLIGHT, width=2.5), marker=dict(size=6),
                             hovertemplate=f"%{{x}}<br>{name or 'valor'}: {hover(pct, decimals, suffix)}<extra></extra>"))  # fmt: skip
    fig.update_layout(title=title(conclusion, subtitle), showlegend=bool(context))
    if pct:
        pct_axis(fig, "y")
    elif suffix:
        fig.update_yaxes(ticksuffix=suffix)
    return fig


def bar(
    categories: Sequence,
    values: Sequence,
    conclusion: str,
    subtitle: str,
    highlight: set | None = None,
    pct: bool = False,
    suffix: str = "",
    decimals: int = 1,
    horizontal: bool = True,
    colors: Sequence[str] | None = None,
    text: Sequence[str] | None = None,
) -> go.Figure:
    """Sorted bar chart. Highlighted categories in blue, the rest grey."""
    highlight = highlight or set()
    if colors is None:
        colors = [HIGHLIGHT if c in highlight else CONTEXT for c in categories]
    labels = list(text) if text is not None else None
    vals = scale(values, pct)
    if horizontal:
        trace = go.Bar(y=list(categories), x=vals, orientation="h", marker=dict(color=list(colors)),
                       text=labels, textposition="outside", cliponaxis=False,
                       hovertemplate=f"%{{y}}: {hover(pct, decimals, suffix, 'x')}<extra></extra>")  # fmt: skip
    else:
        trace = go.Bar(x=list(categories), y=vals, marker=dict(color=list(colors)),
                       text=labels, textposition="outside", cliponaxis=False,
                       hovertemplate=f"%{{x}}: {hover(pct, decimals, suffix)}<extra></extra>")  # fmt: skip
    fig = go.Figure(trace)
    fig.update_layout(title=title(conclusion, subtitle), showlegend=False)
    axis = "x" if horizontal else "y"
    if horizontal:
        fig.update_xaxes(gridcolor=theme.GRID, showgrid=True, rangemode="tozero")
        fig.update_yaxes(autorange="reversed", showgrid=False)
    if pct:
        pct_axis(fig, axis)
    elif suffix:
        (fig.update_xaxes if horizontal else fig.update_yaxes)(ticksuffix=suffix)
    return fig


def tint(hex_color: str, strength: float = 0.35) -> str:
    """Mix a colour with the surface so dark text stays readable on it."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    mix = [round(c * strength + 252 * (1 - strength)) for c in (r, g, b)]
    return f"rgb({mix[0]}, {mix[1]}, {mix[2]})"


def status_heatmap(
    matrix: pd.DataFrame, status: pd.DataFrame, conclusion: str, subtitle: str
) -> go.Figure:
    """Rows x columns grid coloured by status (never by raw value), with value + icon in each cell."""
    order = ["green", "amber", "red", "n/a"]
    z = status.replace({s: i for i, s in enumerate(order)}).astype(float).to_numpy()
    scale_ = []
    for i, s in enumerate(order):
        lo, hi = i / len(order), (i + 1) / len(order)
        scale_ += [[lo, tint(theme.STATUS[s])], [hi, tint(theme.STATUS[s])]]
    labels = [
        [
            ("no medible" if pd.isna(v) else f"{theme.STATUS_ICON[s]} {v * 100:.1f} %")
            for v, s in zip(row_v, row_s, strict=True)
        ]
        for row_v, row_s in zip(matrix.to_numpy(), status.to_numpy(), strict=True)
    ]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=list(matrix.columns),
            y=list(matrix.index),
            colorscale=scale_,
            zmin=0,
            zmax=len(order),
            showscale=False,
            text=labels,
            texttemplate="%{text}",
            xgap=3,
            ygap=3,
            textfont=dict(color=INK, size=13),
            hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
        )  # fmt: skip
    )
    fig.update_layout(title=title(conclusion, subtitle))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showline=False, ticks="")
    return fig


# --------------------------------------------------------------------------- KPI-aware charts
def _engine_helpers():
    from ..engine import format_value, grade

    return format_value, grade


def hover_kpi(k, label: str, value: float, n: float | None = None, n_label: str = "") -> str:
    """Spanish hover text: 'mar 2024 · 0.9 h · Meta ≤ 2.0 h · 🟢 En meta · 1.1 h por debajo de la meta · 312 solicitudes'."""
    format_value, grade = _engine_helpers()
    from ..engine import format_threshold

    if value is None or pd.isna(value):
        return f"{label} · sin dato"
    status = grade(k, value)
    parts = [label, format_value(k, value), f"Meta {format_threshold(k, with_alert=False)}",
             f"{theme.STATUS_ICON[status]} {theme.STATUS_TEXT[status]}"]  # fmt: skip
    if k.direction != "target_range":
        diff = value - k.target
        above = "por encima" if diff > 0 else "por debajo"
        if abs(diff) > 1e-9:
            d = (
                format_value(k, abs(diff)).replace(" %", " puntos")
                if k.unit == "percent"
                else format_value(k, abs(diff))
            )
            parts.append(f"{d} {above} de la meta")
    if n is not None and n_label:
        parts.append(f"{n:,.0f} {n_label}".replace(",", " "))
    return " · ".join(parts)


def _zones(k):
    """(green, amber) intervals on the KPI scale, for shading."""
    g, a = k.thresholds["green"], k.thresholds["amber"]
    top = 1.0 if k.unit == "percent" else max(g, a) * 3
    if k.direction == "higher_is_better":
        return [(g, top)], [(a, g)]
    if k.direction == "lower_is_better":
        return [(0, g)], [(g, a)]
    return [(g[0], g[1])], [(a[0], g[0]), (g[1], a[1])]


def kpi_trend(k, x: Sequence, y: Sequence, conclusion: str, subtitle: str, events: list[tuple] | None = None,
              n: Sequence | None = None, n_label: str = "", y_range: tuple | None = None) -> go.Figure:  # fmt: skip
    """Time series with the target zone (green), the alert zone (amber) and annotated events."""
    pct = k.unit == "percent"
    m = 100 if pct else 1
    fig = go.Figure()
    green, amber = _zones(k)
    for lo, hi in green:
        fig.add_hrect(
            y0=lo * m, y1=hi * m, fillcolor="rgba(12,163,12,0.08)", line_width=0, layer="below"
        )
    for lo, hi in amber:
        fig.add_hrect(
            y0=lo * m, y1=hi * m, fillcolor="rgba(250,178,25,0.12)", line_width=0, layer="below"
        )
    texts = [
        hover_kpi(k, str(xi), yi, None if n is None else n[i], n_label)
        for i, (xi, yi) in enumerate(zip(x, y, strict=True))
    ]
    format_value, grade = _engine_helpers()
    colors = [
        theme.STATUS[grade(k, v)] if v is not None and not pd.isna(v) else theme.CONTEXT for v in y
    ]
    fig.add_trace(go.Scatter(x=list(x), y=scale(y, pct), mode="lines+markers", name=k.name, customdata=texts,
                             line=dict(color=HIGHLIGHT, width=2.5), marker=dict(size=8, color=colors, line=dict(color="white", width=1)),
                             hovertemplate="%{customdata}<extra></extra>"))  # fmt: skip
    for ev in events or []:
        ex, etext = ev[0], ev[1]
        ey = ev[2] if len(ev) > 2 else None
        if ey is None:
            idx = list(x).index(ex) if ex in list(x) else None
            ey = (y[idx] * m) if idx is not None and y[idx] is not None else None
        if ey is not None:
            annotate(fig, ex, ey, etext, ay=-45)
    fig.add_annotation(xref="paper", x=1, y=(green[0][1] if k.direction == "higher_is_better" else green[0][0]) * m if k.direction != "target_range" else green[0][1] * m,
                       text="zona en meta", showarrow=False, xanchor="right", yanchor="bottom" if k.direction != "higher_is_better" else "top",
                       font=dict(size=10, color="#006300"))  # fmt: skip
    fig.update_layout(title=title(conclusion, subtitle), showlegend=False)
    if pct:
        pct_axis(fig, "y")
    else:
        fig.update_yaxes(ticksuffix={"hours": " h", "days": " d"}.get(k.unit, ""))
    if y_range:
        fig.update_yaxes(range=list(y_range))
    return fig


def bullets(items: list[tuple], conclusion: str, subtitle: str) -> go.Figure:
    """Bullet charts, one row per KPI: amber/green ranges, value bar and target tick.

    items: (kpi, value). Each row is normalised to the KPI's own scale and labelled with its value.
    """
    from plotly.subplots import make_subplots

    format_value, grade = _engine_helpers()
    from ..engine import format_threshold

    fig = make_subplots(rows=len(items), cols=1, vertical_spacing=0.32 / max(1, len(items)) + 0.06)
    for i, (k, v) in enumerate(items, start=1):
        pct = k.unit == "percent"
        m = 100 if pct else 1
        g, a = k.thresholds["green"], k.thresholds["amber"]
        if k.direction == "target_range":
            top = a[1] * 1.3
        elif k.direction == "lower_is_better":
            top = max(a * 1.6, (v or 0) * 1.1)
        else:
            top = 1.0 if pct else max(g * 1.4, (v or 0) * 1.1)
        top = min(top, 1.0) if pct else top
        status = grade(k, v)
        # background ranges
        if k.direction == "higher_is_better":
            ranges = [
                (0, a, "rgba(208,59,59,0.12)"),
                (a, g, "rgba(250,178,25,0.22)"),
                (g, top, "rgba(12,163,12,0.15)"),
            ]
        elif k.direction == "lower_is_better":
            ranges = [
                (0, g, "rgba(12,163,12,0.15)"),
                (g, a, "rgba(250,178,25,0.22)"),
                (a, top, "rgba(208,59,59,0.12)"),
            ]
        else:
            ranges = [(0, a[0], "rgba(208,59,59,0.12)"), (a[0], g[0], "rgba(250,178,25,0.22)"), (g[0], g[1], "rgba(12,163,12,0.15)"),
                      (g[1], a[1], "rgba(250,178,25,0.22)"), (a[1], top, "rgba(208,59,59,0.12)")]  # fmt: skip
        for lo, hi, col in ranges:
            fig.add_trace(go.Bar(x=[(hi - lo) * m], base=[lo * m], y=[""], orientation="h", marker_color=col, width=0.9,
                                 hoverinfo="skip", showlegend=False), row=i, col=1)  # fmt: skip
        fig.add_trace(go.Bar(x=[(v or 0) * m], y=[""], orientation="h", marker_color=theme.INK_2, width=0.32, showlegend=False,
                             customdata=[hover_kpi(k, k.name, v)], hovertemplate="%{customdata}<extra></extra>"), row=i, col=1)  # fmt: skip
        tgt = k.target * m
        fig.add_shape(
            type="line",
            x0=tgt,
            x1=tgt,
            y0=-0.45,
            y1=0.45,
            line=dict(color=INK, width=3),
            row=i,
            col=1,
        )
        fig.update_xaxes(
            range=[0, top * m], showgrid=False, ticksuffix=" %" if pct else "", row=i, col=1
        )
        fig.update_yaxes(showticklabels=False, row=i, col=1)
        fig.add_annotation(text=f"<b>{k.name}</b>: {format_value(k, v)} {theme.STATUS_ICON[status]} · meta {format_threshold(k, with_alert=False)}",
                           xref=f"x{i if i > 1 else ''} domain", yref=f"y{i if i > 1 else ''} domain", x=0, y=1.08, yanchor="bottom", showarrow=False,
                           xanchor="left", font=dict(size=12, color=INK))  # fmt: skip
    fig.update_layout(
        barmode="overlay", title=title(conclusion, subtitle), showlegend=False, bargap=0
    )
    return fig


def pareto(
    categories: Sequence, values: Sequence, conclusion: str, subtitle: str, unit_label: str
) -> go.Figure:
    """Sorted bars plus the cumulative share line (one axis per panel: share on a secondary scale is avoided)."""
    from plotly.subplots import make_subplots

    s = pd.Series(list(values), index=list(categories)).sort_values(ascending=False)
    cum = s.cumsum() / s.sum() * 100
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.06
    )
    top = set(cum.index[: int((cum < 80).sum()) + 1])
    fig.add_trace(go.Bar(x=list(s.index), y=list(s.values), marker_color=[HIGHLIGHT if c in top else CONTEXT for c in s.index],
                         text=[f"{v:,.0f}".replace(",", " ") for v in s.values], textposition="outside", cliponaxis=False,
                         customdata=[f"{c} · {v:,.0f} {unit_label} · {p:.0f} % acumulado".replace(",", " ") for c, v, p in zip(s.index, s.values, cum.values, strict=True)],
                         hovertemplate="%{customdata}<extra></extra>", showlegend=False), row=1, col=1)  # fmt: skip
    fig.add_trace(go.Scatter(x=list(cum.index), y=list(cum.values), mode="lines+markers", line=dict(color=INK_2, width=2),
                             customdata=[f"{c} · {p:.0f} % acumulado" for c, p in cum.items()],
                             hovertemplate="%{customdata}<extra></extra>", showlegend=False), row=2, col=1)  # fmt: skip
    fig.add_hline(
        y=80,
        line=dict(color=theme.MUTED, width=1),
        row=2,
        col=1,
        annotation_text="80 %",
        annotation_position="top left",
    )
    fig.update_yaxes(title_text=unit_label, row=1, col=1)
    fig.update_yaxes(title_text="acumulado", ticksuffix=" %", range=[0, 105], row=2, col=1)
    fig.update_layout(title=title(conclusion, subtitle))
    return fig


def waterfall(start_label: str, start: float, steps: list[tuple[str, float]], end_label: str, conclusion: str,
              subtitle: str, unit_label: str) -> go.Figure:  # fmt: skip
    """From month A to month B: which group explains the change."""
    labels = [start_label] + [s[0] for s in steps] + [end_label]
    values = [start] + [s[1] for s in steps] + [start + sum(s[1] for s in steps)]
    measure = ["absolute"] + ["relative"] * len(steps) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measure, connector=dict(line=dict(color=theme.AXIS, width=1)),
        increasing=dict(marker=dict(color=theme.SECOND)), decreasing=dict(marker=dict(color=theme.THIRD)),
        totals=dict(marker=dict(color=CONTEXT)), text=[f"{v:+,.0f}".replace(",", " ") if m == "relative" else f"{v:,.0f}".replace(",", " ") for v, m in zip(values, measure, strict=True)],
        textposition="outside", customdata=[f"{lab} · {v:+,.0f} {unit_label}".replace(",", " ") if m == "relative" else f"{lab} · {v:,.0f} {unit_label}".replace(",", " ")
                                            for lab, v, m in zip(labels, values, measure, strict=True)],
        hovertemplate="%{customdata}<extra></extra>"))  # fmt: skip
    fig.update_layout(title=title(conclusion, subtitle), showlegend=False)
    fig.update_yaxes(title_text=unit_label)
    return fig


def small_multiples(k, groups: dict[str, tuple[Sequence, Sequence]], conclusion: str, subtitle: str,
                    highlight: set | None = None, cols: int = 3) -> go.Figure:  # fmt: skip
    """One small panel per group, same scale, target line in each; highlighted groups in blue."""
    from plotly.subplots import make_subplots

    highlight = highlight or set()
    names = list(groups)
    rows = math.ceil(len(names) / cols)
    pct = k.unit == "percent"
    m = 100 if pct else 1
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=names,
        shared_yaxes=True,
        vertical_spacing=0.16,
        horizontal_spacing=0.05,
    )
    all_y = [v for _, (_, y) in groups.items() for v in y if v is not None and not pd.isna(v)]
    lo, hi = (min(all_y + [k.target]) * m, max(all_y + [k.target]) * m) if all_y else (0, 1)
    pad = (hi - lo) * 0.1 or 1
    for i, name in enumerate(names):
        r, c = i // cols + 1, i % cols + 1
        x, y = groups[name]
        color = HIGHLIGHT if name in highlight else theme.CONTEXT_DARK
        fig.add_trace(go.Scatter(x=list(x), y=scale(y, pct), mode="lines", line=dict(color=color, width=2.2 if name in highlight else 1.5),
                                 customdata=[hover_kpi(k, f"{name} · {xi}", yi) for xi, yi in zip(x, y, strict=True)],
                                 hovertemplate="%{customdata}<extra></extra>", showlegend=False), row=r, col=c)  # fmt: skip
        fig.add_hline(y=k.target * m, line=dict(color=INK_2, width=1, dash="dot"), row=r, col=c)
        fig.update_xaxes(
            showticklabels=r == rows or i + cols >= len(names), tickangle=0, nticks=4, row=r, col=c
        )
    fig.update_yaxes(
        range=[lo - pad, hi + pad], ticksuffix=" %" if pct else "", gridcolor=theme.GRID
    )
    fig.update_annotations(font=dict(size=12, color=INK))
    fig.update_layout(title=title(conclusion, subtitle))
    return fig


def scenario(k, esc, conclusion: str, subtitle: str, hist_labels: Sequence) -> go.Figure:
    """History, then two projections after the decision: without (grey) and with (blue)."""
    pct = k.unit == "percent"
    m = 100 if pct else 1
    fig = go.Figure()
    green, amber = _zones(k)
    for lo, hi in green:
        fig.add_hrect(
            y0=lo * m, y1=hi * m, fillcolor="rgba(12,163,12,0.08)", line_width=0, layer="below"
        )
    for lo, hi in amber:
        fig.add_hrect(
            y0=lo * m, y1=hi * m, fillcolor="rgba(250,178,25,0.12)", line_width=0, layer="below"
        )
    hx = list(hist_labels)
    fig.add_trace(go.Scatter(x=hx, y=scale(esc.historia, pct), mode="lines+markers", line=dict(color=INK_2, width=2), name="Antes (datos)",
                             customdata=[hover_kpi(k, f"{a} · dato", b) for a, b in zip(hx, esc.historia, strict=True)],
                             hovertemplate="%{customdata}<extra></extra>"))  # fmt: skip
    px = [hx[-1]] + esc.meses
    fig.add_trace(go.Scatter(x=px, y=scale([esc.historia[-1]] + esc.sin_decision, pct), mode="lines", line=dict(color=CONTEXT, width=2, dash="dot"),
                             name="Sin la decisión (simulado)", customdata=[""] + [hover_kpi(k, f"{a} · sin la decisión", b) for a, b in zip(esc.meses, esc.sin_decision, strict=True)],
                             hovertemplate="%{customdata}<extra></extra>"))  # fmt: skip
    fig.add_trace(go.Scatter(x=px, y=scale([esc.historia[-1]] + esc.con_decision, pct), mode="lines+markers", line=dict(color=HIGHLIGHT, width=2.5),
                             name="Con la decisión (simulado)", customdata=[""] + [hover_kpi(k, f"{a} · con la decisión", b) for a, b in zip(esc.meses, esc.con_decision, strict=True)],
                             hovertemplate="%{customdata}<extra></extra>"))  # fmt: skip
    fig.add_vline(x=esc.meses[0], line=dict(color=INK, width=1))
    fig.add_annotation(x=esc.meses[0], y=1, yref="paper", text="se aplica la decisión", showarrow=False, xanchor="left", yanchor="top",
                       font=dict(size=11, color=INK))  # fmt: skip
    fig.update_layout(title=title(conclusion, subtitle), showlegend=True)
    if pct:
        pct_axis(fig, "y")
    return fig


def table_from_figure(fig: go.Figure) -> pd.DataFrame:
    """Fallback data table: every trace's x/y (and hover text) so no chart is mouse-only."""
    rows = []
    for tr in fig.data:
        name = getattr(tr, "name", None) or ""
        if tr.type == "box":
            vals = pd.Series(list(tr.y) if tr.y is not None else []).dropna()
            if len(vals):
                rows.append(
                    {"Serie": name, "Categoría o fecha": "casos", "Valor": len(vals), "Detalle": ""}
                )
                rows.append(
                    {
                        "Serie": name,
                        "Categoría o fecha": "típico (mediana)",
                        "Valor": round(float(vals.median()), 2),
                        "Detalle": "",
                    }
                )
                rows.append(
                    {
                        "Serie": name,
                        "Categoría o fecha": "promedio",
                        "Valor": round(float(vals.mean()), 2),
                        "Detalle": "",
                    }
                )
                rows.append(
                    {
                        "Serie": name,
                        "Categoría o fecha": "máximo",
                        "Valor": round(float(vals.max()), 2),
                        "Detalle": "",
                    }
                )
            continue
        if tr.type in ("scatter", "bar", "waterfall", "histogram"):
            xs = list(tr.x) if tr.x is not None else []
            ys = list(tr.y) if tr.y is not None else []
            if getattr(tr, "orientation", None) == "h":
                xs, ys = ys, xs
            cd = (
                list(tr.customdata)
                if getattr(tr, "customdata", None) is not None
                else [None] * len(xs)
            )
            for i, xv in enumerate(xs):
                yv = ys[i] if i < len(ys) else None
                det = cd[i] if i < len(cd) else None
                if not isinstance(det, str):
                    det = None
                rows.append(
                    {
                        "Serie": name,
                        "Categoría o fecha": xv,
                        "Valor": None
                        if yv is None
                        else (round(yv, 2) if isinstance(yv, float) else yv),
                        "Detalle": det or "",
                    }
                )
        elif tr.type == "heatmap":
            for yi, row in zip(tr.y, tr.text, strict=False):
                for xi, cell in zip(tr.x, row, strict=False):
                    rows.append(
                        {"Serie": yi, "Categoría o fecha": xi, "Valor": cell, "Detalle": ""}
                    )
        elif tr.type == "pie":
            for lab, val in zip(tr.labels, tr.values, strict=False):
                rows.append({"Serie": "", "Categoría o fecha": lab, "Valor": val, "Detalle": ""})
    df = pd.DataFrame(rows)
    if not df.empty and df["Detalle"].eq("").all():
        df = df.drop(columns="Detalle")
    if not df.empty and df["Serie"].eq("").all():
        df = df.drop(columns="Serie")
    return df.head(400)
