"""Chart helpers. Each returns a Plotly figure that already follows the house rules.

Percentages are passed as fractions (0.89) and drawn as "89 %" (value x 100 with a
" %" suffix), because Plotly's own percent format has no space before the sign.
"""

from __future__ import annotations

import html
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
    if table is not None:
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
