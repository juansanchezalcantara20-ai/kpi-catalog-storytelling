"""Chart helpers. Each returns a Plotly figure that already follows the house rules."""

from __future__ import annotations

import html
from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go

from . import theme
from .theme import CONTEXT, HIGHLIGHT, INK, INK_2, title

CONFIG = {"displayModeBar": False, "responsive": True}
_counter = {"n": 0}


def to_html(
    fig: go.Figure, height: int = 400, table: pd.DataFrame | None = None, caption: str = ""
) -> str:
    """Figure -> HTML snippet for a Markdown page, followed by an optional data table."""
    _counter["n"] += 1
    title_text = fig.layout.title.text or ""
    extra = 20 * title_text.count("<br>")
    fig.update_layout(
        height=height + extra, autosize=True, margin=dict(t=60 + 20 * title_text.count("<br>") + 16)
    )
    div = fig.to_html(
        full_html=False, include_plotlyjs=False, config=CONFIG, div_id=f"chart-{_counter['n']}"
    )
    out = f'<div class="chart" markdown="0">\n{div}\n</div>\n'
    if caption:
        out += f'<p class="chart-caption">{html.escape(caption)}</p>\n'
    if table is not None:
        out += data_table(table)
    return out + "\n"


def data_table(df: pd.DataFrame, summary: str = "Show the data behind this chart") -> str:
    body = df.to_html(index=False, border=0, classes="data-table", na_rep="–", escape=True)
    return f"<details class='data'><summary>{summary}</summary>\n{body}\n</details>\n"


def add_target(fig: go.Figure, value: float, label: str, axis: str = "y") -> None:
    """Thin solid reference line with a direct label (no legend entry)."""
    if axis == "y":
        fig.add_hline(y=value, line=dict(color=INK_2, width=1), layer="below",
                      annotation=dict(text=label, font=dict(color=INK_2, size=12), xanchor="left", x=0),
                      annotation_position="top left")  # fmt: skip
    else:
        fig.add_vline(x=value, line=dict(color=INK_2, width=1), layer="below",
                      annotation=dict(text=label, font=dict(color=INK_2, size=12)), annotation_position="top")  # fmt: skip


def add_band(fig: go.Figure, low: float, high: float, axis: str = "y") -> None:
    """Shaded green band for target-range KPIs."""
    if axis == "y":
        fig.add_hrect(y0=low, y1=high, fillcolor=theme.BAND_FILL, line_width=0, layer="below")
    else:
        fig.add_vrect(x0=low, x1=high, fillcolor=theme.BAND_FILL, line_width=0, layer="below")


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
    yformat: str = ".0%",
    context: dict[str, tuple[Sequence, Sequence]] | None = None,
) -> go.Figure:
    """One highlighted line; optional context lines in grey, labelled at their end."""
    fig = go.Figure()
    for cname, (cx, cy) in (context or {}).items():
        fig.add_trace(go.Scatter(x=list(cx), y=list(cy), name=cname, mode="lines",
                                 line=dict(color=CONTEXT, width=1.5), hovertemplate=f"{cname}: %{{y:{yformat}}}<extra></extra>"))  # fmt: skip
    fig.add_trace(go.Scatter(x=list(x), y=list(y), name=name or "value", mode="lines+markers",
                             line=dict(color=HIGHLIGHT, width=2.5), marker=dict(size=6),
                             hovertemplate=f"%{{x}}<br>{name or 'value'}: %{{y:{yformat}}}<extra></extra>"))  # fmt: skip
    fig.update_layout(title=title(conclusion, subtitle), showlegend=bool(context))
    fig.update_yaxes(tickformat=yformat)
    return fig


def bar(
    categories: Sequence,
    values: Sequence,
    conclusion: str,
    subtitle: str,
    highlight: set | None = None,
    xformat: str = ".0%",
    horizontal: bool = True,
    colors: Sequence[str] | None = None,
    text: Sequence[str] | None = None,
) -> go.Figure:
    """Sorted bar chart. Highlighted categories in blue, the rest grey."""
    highlight = highlight or set()
    if colors is None:
        colors = [HIGHLIGHT if c in highlight else CONTEXT for c in categories]
    labels = list(text) if text is not None else None
    if horizontal:
        trace = go.Bar(y=list(categories), x=list(values), orientation="h", marker=dict(color=list(colors)),
                       text=labels, textposition="outside", cliponaxis=False,
                       hovertemplate=f"%{{y}}: %{{x:{xformat}}}<extra></extra>")  # fmt: skip
    else:
        trace = go.Bar(x=list(categories), y=list(values), marker=dict(color=list(colors)),
                       text=labels, textposition="outside", cliponaxis=False,
                       hovertemplate=f"%{{x}}: %{{y:{xformat}}}<extra></extra>")  # fmt: skip
    fig = go.Figure(trace)
    fig.update_layout(title=title(conclusion, subtitle), showlegend=False)
    if horizontal:
        fig.update_xaxes(
            tickformat=xformat, gridcolor=theme.GRID, showgrid=True, rangemode="tozero"
        )
        fig.update_yaxes(autorange="reversed", showgrid=False)
    else:
        fig.update_yaxes(tickformat=xformat)
    return fig


def tint(hex_color: str, strength: float = 0.35) -> str:
    """Mix a colour with the surface so dark text stays readable on it."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    mix = [round(c * strength + 252 * (1 - strength)) for c in (r, g, b)]
    return f"rgb({mix[0]}, {mix[1]}, {mix[2]})"


def status_heatmap(
    matrix: pd.DataFrame, status: pd.DataFrame, conclusion: str, subtitle: str, fmt: str = "{:.1%}"
) -> go.Figure:
    """Rows x columns grid coloured by status (never by raw value), with value + icon in each cell."""
    order = ["green", "amber", "red", "n/a"]
    z = status.replace({s: i for i, s in enumerate(order)}).astype(float).to_numpy()
    scale = []
    for i, s in enumerate(order):
        lo, hi = i / len(order), (i + 1) / len(order)
        scale += [[lo, tint(theme.STATUS[s])], [hi, tint(theme.STATUS[s])]]
    labels = [
        [
            ("not measurable" if pd.isna(v) else f"{theme.STATUS_ICON[s]} {fmt.format(v)}")
            for v, s in zip(row_v, row_s, strict=True)
        ]
        for row_v, row_s in zip(matrix.to_numpy(), status.to_numpy(), strict=True)
    ]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=list(matrix.columns),
            y=list(matrix.index),
            colorscale=scale,
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
