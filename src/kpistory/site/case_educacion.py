"""Educación: alumnos por docente en Sudamérica (UNESCO vía TidyTuesday)."""

from __future__ import annotations

import pandas as pd

from ..engine import Engine, format_value
from ..viz import charts, theme
from .common import aviso_datos, pct
from .current import headline
from .plantilla import pagina, resultado_estimado

CASO = "educacion"
PAIS = "Perú"


def build(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> str:
    H = headline(t, e, manifest)
    d = t["docentes"]
    k = e.catalog["pupil_teacher_ratio"]
    y = int(d["year"].max())
    rec = d[d["year"] >= y - 2]
    by_lvl = e.compute_by("pupil_teacher_ratio", rec, "level").sort_values("value", ascending=False)
    by_c = e.compute_by("pupil_teacher_ratio", rec, ["country", "level"])
    worst = by_c.sort_values("value", ascending=False).iloc[0]
    over = by_c[by_c["value"] > k.target]
    lvl = by_lvl.iloc[0]
    sub = by_c[by_c["level"].eq(lvl["level"])].sort_values("value", ascending=False)

    g1 = charts.bar(
        by_lvl["level"], by_lvl["value"], decimals=1,
        colors=[theme.STATUS[e.status("pupil_teacher_ratio", v)] for v in by_lvl["value"]],
        text=[format_value(k, v) for v in by_lvl["value"]],
        conclusion=f"El nivel con más alumnos por docente es «{lvl['level']}»: {format_value(k, lvl['value'])}",
        subtitle=f"Registro típico (mediana) de los países de Sudamérica, {y - 2} a {y}; color = semáforo frente a la meta de 20",
    )  # fmt: skip
    g2 = charts.bar(
        sub["country"], sub["value"], decimals=1, highlight={PAIS},
        colors=[theme.HIGHLIGHT if c == PAIS else theme.STATUS[e.status("pupil_teacher_ratio", v)] for c, v in zip(sub["country"], sub["value"], strict=True)],
        text=[format_value(k, v) for v in sub["value"]],
        conclusion=f"En «{lvl['level']}», «{sub.iloc[0]['country']}» tiene la mayor carga: {format_value(k, sub.iloc[0]['value'])}",
        subtitle=f"Alumnos por docente en «{lvl['level']}» por país, {y - 2} a {y}; {PAIS} en azul",
    )  # fmt: skip
    groups = {
        lv: (list(g["year"]), g["student_ratio"].tolist())
        for lv, g in d[d["country"].eq(PAIS)].sort_values("year").groupby("level")
    }
    g3 = charts.small_multiples(
        k, groups, cols=3,
        conclusion=f"En {PAIS} la relación se mantiene estable en cada nivel",
        subtitle=f"Alumnos por docente en {PAIS} por nivel y año; línea punteada = meta",
    )  # fmt: skip
    analisis = (
        f"**Por nivel.** Mezclar niveles en un solo número esconde dónde falta personal.\n\n{charts.to_html(g1, height=360)}\n"
        f"**Por país, en el nivel más cargado.**\n\n{charts.to_html(g2, height=400)}\n"
        f"**{PAIS} en el tiempo.**\n\n{charts.to_html(g3, height=340)}"
    )
    extra = worst["value"] / k.target - 1
    resultado = resultado_estimado(
        f"- **Escenario:** llevar «{worst['country']} · {worst['level']}» de {format_value(k, worst['value'])} a la meta de 20 exige "
        f"**{pct(extra)} más docentes** en ese nivel (cálculo: valor actual / 20 − 1), con la misma cantidad de alumnos.\n"
        f"- **{len(over)} combinaciones** de país y nivel están por encima de la meta en {y - 2} a {y}.\n"
        "- No es un resultado observado: la fuente no registra ninguna decisión, y el aprendizaje (el resultado que importa) no está en estos datos."
    )
    return pagina(
        CASO, e, H, manifest,
        titulo="Alumnos por docente: ¿dónde falta personal?",
        aviso=aviso_datos(manifest, ["docentes"]),
        en30=(
            f"El nivel más cargado de Sudamérica es «{lvl['level']}» ({format_value(k, lvl['value'])}); {PAIS} tiene "
            f"{format_value(k, H['pupil_teacher_ratio'].value)} ({H['pupil_teacher_ratio'].period}).",
            "Los docentes son el principal costo de un colegio y, a la vez, la principal palanca de calidad: hay que asignarlos donde más faltan.",
            f"Asignar las nuevas plazas primero a los grupos por encima de 25, empezando por «{worst['country']} · {worst['level']}».",
        ),
        problema=(
            "Una red de colegios, o un sistema educativo, decide cada año cuántas plazas docentes abre y dónde. La relación de alumnos por "
            "docente dice dónde la carga es mayor. Este caso compara países y niveles, como grupos, con datos públicos de la UNESCO."
        ),
        pregunta_negocio="¿En qué nivel y en qué grupo la carga por docente supera la meta?",
        analisis=analisis,
        solucion=(
            "1. **Asignar las nuevas plazas** a los grupos con más de 25 alumnos por docente.\n"
            "2. **Revisar los grupos con muy pocos alumnos por docente**: pueden tener un costo por alumno alto sin mejorar el aprendizaje.\n"
            "3. **Medir el aprendizaje** (pruebas estandarizadas) junto a este indicador: es el resultado que falta."
        ),
        resultado=resultado,
        tecnico=(
            "- Tabla `docentes`: una fila por país, nivel y año, con `student_ratio` (alumnos por docente publicado por la UNESCO).\n"
            "- El indicador es la mediana de los registros; no hay cantidades de alumnos para ponderar por tamaño.\n"
            "- Niveles: primaria y los dos ciclos de secundaria; no todos los países publican todos los años."
        ),
    )  # fmt: skip
