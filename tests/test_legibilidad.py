"""Prueba de legibilidad del sitio publicado (corre sobre el HTML que genera `mkdocs build`).

Fuera de los bloques «Detalle técnico», ninguna página puede tener:
  * palabras en snake_case ni palabras técnicas en inglés de la lista negra;
  * siglas sin explicar en su página (SLA, FCR, KPI) ni códigos prohibidos (P90, P1 a P4);
  * trimestres escritos como «2024Q4»;
  * bloques de código.
También revisa los textos de los gráficos y de las tarjetas del tablero.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

bs4 = pytest.importorskip("bs4")

SITE = Path(__file__).resolve().parents[1] / "site"
REQUIRE = os.environ.get("KPISTORY_REQUIRE_SITE") == "1"

BLACKLIST = [
    "Watch", "Act", "bucket", "buckets", "queue", "queues", "median", "backlog", "compliance", "rate", "Case",
    "Finding", "Findings", "Decision", "Decisions", "Target", "Owner", "Show", "chart", "story", "Share", "Overview",
    "ticket", "tickets", "average", "Context", "Question", "Monitoring", "On target", "lead time", "fill rate",
]  # fmt: skip
SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
QUARTER = re.compile(r"\b\d{4}\s?Q[1-4]\b")
FORBIDDEN_CODES = re.compile(r"\bP90\b|\bP[1-4]\b")
EXPLAIN = {
    "SLA": "plazo comprometido con el cliente",
    "FCR": "resuelto en el primer contacto",
    "KPI": "indicador",
}
PLOTLY_TEXT = re.compile(
    r'"(?:text|name|hovertemplate|ticktext)":\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\])'
)


def _pages() -> list[Path]:
    if not SITE.exists():
        if REQUIRE:
            pytest.fail("No existe site/: corre `mkdocs build` antes de esta prueba.")
        pytest.skip("site/ no existe; corre `make all` primero")
    return sorted(p for p in SITE.rglob("index.html") if "search" not in p.parts) + sorted(
        SITE.glob("404.html")
    )


def _visible_text(path: Path) -> tuple[str, list[str]]:
    """Visible text outside «Detalle técnico», plus chart/dashboard strings, plus code blocks found."""
    soup = bs4.BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    chart_strings: list[str] = []
    for script in soup.find_all("script"):
        src = script.string or ""
        if "Plotly.newPlot" in src:
            for m in PLOTLY_TEXT.finditer(src):
                raw = m.group(1)
                try:
                    val = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                chart_strings += val if isinstance(val, list) else [val]
        if "const DATA =" in src:
            data = json.loads(src.split("const DATA =", 1)[1].split(";\nconst ICON", 1)[0])
            for k in data["kpis"]:
                chart_strings += [
                    k["name"],
                    k["question"],
                    k["meaning"],
                    k["how_to_read"],
                    k["display"],
                    k["period"],
                    *k["misreadings"],
                ]
                chart_strings += [k["series"].get("label", ""), *map(str, k["series"]["x"])]
            chart_strings += list(data["cases"].values()) + [data["data_note"]]
    for tag in soup.find_all(["script", "style", "svg"]):
        tag.decompose()
    for tag in soup.select("details.tecnico"):
        tag.decompose()
    code = [c.get_text()[:40] for c in soup.find_all(["pre", "code"])]
    text = soup.get_text(" ", strip=True)
    strings = " ".join(str(s) for s in chart_strings if isinstance(s, str))
    strings = re.sub(r"%\{[^}]*\}|<[^>]+>", " ", strings)  # Plotly placeholders and inline tags
    return text + " " + strings, code


def _problems(path: Path) -> list[str]:
    text, code = _visible_text(path)
    found = []
    if code:
        found.append(f"bloques de código fuera del detalle técnico: {code[:3]}")
    for word in BLACKLIST:
        if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text):
            found.append(f"palabra en inglés: «{word}»")
    snakes = sorted(set(SNAKE.findall(text)))
    if snakes:
        found.append(f"nombres internos sin etiqueta: {snakes[:5]}")
    if QUARTER.search(text):
        found.append(f"trimestre mal escrito: «{QUARTER.search(text).group(0)}»")
    if FORBIDDEN_CODES.search(text):
        found.append(f"código no explicado: «{FORBIDDEN_CODES.search(text).group(0)}»")
    for sigla, explanation in EXPLAIN.items():
        m = re.search(rf"\b{sigla}\b", text)
        if m:
            window = text[max(0, m.start() - 160) : m.end() + 160].lower()
            if explanation not in window:
                found.append(f"sigla «{sigla}» sin explicar donde aparece por primera vez")
    return found


def test_hay_paginas_publicadas():
    assert len(_pages()) > 30


def test_todas_las_paginas_son_legibles():
    report = {str(p.relative_to(SITE)): problems for p in _pages() if (problems := _problems(p))}
    assert not report, "Problemas de legibilidad:\n" + "\n".join(
        f"- {page}: {'; '.join(v)}" for page, v in report.items()
    )


def test_la_prueba_detecta_lo_que_debe(tmp_path):
    bad = tmp_path / "index.html"
    bad.write_text(
        "<html><body><p>SLA compliance 2024Q4 for P1 tickets in the queue_name</p><pre>x</pre>"
        "<details class='tecnico'><p>queue_name is fine here</p></details></body></html>",
        encoding="utf-8",
    )
    problems = " ".join(_problems(bad))
    for expected in ("compliance", "queue_name", "2024Q4", "P1", "SLA", "código"):
        assert expected in problems
