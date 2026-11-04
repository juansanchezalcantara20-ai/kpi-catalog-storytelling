"""Palette and Plotly template shared by every chart (story site and dashboard).

Colours come from a colour-blind-validated categorical order (blue, orange, aqua) and a
reserved status palette. House rules enforced here:
  * one message per chart -> one highlight colour, everything else is context grey;
  * status colours only mean good / watch / act and always travel with an icon + label;
  * titles state the conclusion; the subtitle states what is plotted.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

HIGHLIGHT = "#2a78d6"  # series 1 - the thing the title talks about
SECOND = "#eb6834"  # series 2 - only when a comparison needs it
THIRD = "#1baf7a"  # series 3
CONTEXT = "#c3c2b7"  # everything that is not the message
CONTEXT_DARK = "#898781"

STATUS = {"green": "#0ca30c", "amber": "#fab219", "red": "#d03b3b", "n/a": "#c3c2b7"}
STATUS_ICON = {"green": "✓", "amber": "!", "red": "✕", "n/a": "–"}
STATUS_TEXT = {"green": "On target", "amber": "Watch", "red": "Act", "n/a": "No data"}
BAND_FILL = "rgba(12, 163, 12, 0.08)"  # green target band
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ORDINAL = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT, size=13, color=INK_2),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=[HIGHLIGHT, SECOND, THIRD],
        title=dict(
            font=dict(size=16, color=INK),
            x=0.01,
            xanchor="left",
            xref="container",
            y=1,
            yref="container",
            yanchor="top",
            pad=dict(t=14),
        ),
        margin=dict(l=56, r=28, t=96, b=48),
        xaxis=dict(
            automargin=True,
            showgrid=False,
            linecolor=AXIS,
            ticks="outside",
            tickcolor=AXIS,
            zeroline=False,
        ),
        yaxis=dict(
            automargin=True,
            gridcolor=GRID,
            gridwidth=1,
            zeroline=False,
            linecolor=AXIS,
            rangemode="tozero",
        ),
        legend=dict(
            orientation="h",
            y=1.02,
            yanchor="bottom",
            x=0,
            xanchor="left",
            title_text="",
            traceorder="normal",
        ),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, color=INK)),
        bargap=0.3,
    )
)
pio.templates["kpistory"] = TEMPLATE
pio.templates.default = "kpistory"


def wrap(text: str, width: int = 74) -> str:
    """Break a long title into lines (Plotly does not wrap titles)."""
    words, lines, current = text.split(), [], ""
    for w in words:
        if current and len(current) + 1 + len(w) > width:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    lines.append(current)
    return "<br>".join(lines)


def title(conclusion: str, subtitle: str, width: int = 74) -> dict:
    """Plotly title: the conclusion in bold ink, what is plotted underneath in grey."""
    sub = wrap(subtitle, int(width * 1.3)).replace(
        "<br>", f"</span><br><span style='font-size:13px;color:{INK_2}'>"
    )
    return dict(
        text=f"<b>{wrap(conclusion, width)}</b><br><span style='font-size:13px;color:{INK_2}'>{sub}</span>"
    )
