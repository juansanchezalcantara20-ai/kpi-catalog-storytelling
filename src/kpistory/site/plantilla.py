"""Case template «Problema → Solución → Resultado» and the case/rubro/tema metadata blocks.

Every case page has the same seven parts, in this order:
  1. En 30 segundos   2. Problema   3. Indicadores (resultado, adelantados, contrapeso)
  4. Análisis         5. Solución   6. Resultado (observado en datos reales, o estimado)
  7. Detalle técnico
A test checks the seven parts and the result label on every published case.
"""

from __future__ import annotations

import html

from ..catalog import load, rubros_config
from ..engine import Engine
from .common import ROL_AYUDA, ROL_TEXTO, detalle_tecnico, en_30_segundos, pregunta, tiles
from .current import Headline

# config/fuentes.yaml key -> manifest key
MANIFEST_KEY = {
    "solicitudes": "tickets", "mantenimiento": "process_data", "ventas": "transactions", "energia": "energia",
    "vacunas": "salud", "mortalidad": "salud", "moviles": "moviles", "docentes": "docentes", "vuelos": "vuelos",
    "creditos": "creditos",
}  # fmt: skip
SECCIONES = ["Problema", "Indicadores", "Análisis", "Solución", "Resultado"]
OBSERVADO = "Resultado observado en datos reales"
ESTIMADO = "Resultado estimado (escenario)"


def con_datos_reales(case_id: str, manifest: dict) -> bool:
    """True when every public source of the case arrived and is real (a reference dataset does not count)."""
    from ..data.sectores import fuentes

    keys = load().cases[case_id]["fuentes"]
    return all(
        fuentes()[k].get("tipo") == "real"
        and manifest.get(MANIFEST_KEY[k], {}).get("origin") == "real"
        for k in keys
    )


def tipo_resultado(case_id: str, manifest: dict) -> str:
    """«observado» only with a documented event AND real data this time; otherwise «estimado»."""
    c = load().cases[case_id]
    return (
        "observado"
        if c["resultado"] == "observado" and con_datos_reales(case_id, manifest)
        else "estimado"
    )


def ficha(case_id: str, manifest: dict, depth: int = 1) -> str:
    """Line under the title: rubros and tema with links, plus machine-readable metadata for the tests."""
    cfg = rubros_config()
    c = load().cases[case_id]
    up = "../" * (
        depth + 1
    )  # published pages live in folders: cases/energia/ -> ../../rubros/energia/
    rub = " · ".join(
        f'<a href="{up}rubros/{r}/">{html.escape(cfg["rubros"][r]["nombre"])}</a>'
        for r in c["rubros"]
    )
    tema = f'<a href="{up}temas/{c["tema"]}/">{html.escape(cfg["temas"][c["tema"]]["nombre"])}</a>'
    tipo = tipo_resultado(case_id, manifest)
    real = (
        "con datos reales"
        if con_datos_reales(case_id, manifest)
        else "con datos simulados o de referencia"
    )
    meta = (
        f'<div class="caso-meta" markdown="0" data-caso="{case_id}" data-resultado="{tipo}" '
        f'data-rubros="{" ".join(c["rubros"])}" data-tema="{c["tema"]}" data-reales="{int(con_datos_reales(case_id, manifest))}"></div>'
    )
    return f'<p class="caso-ficha">Rubro: {rub} · Tema: {tema} · Caso {real}</p>\n\n{meta}\n\n'


def indicadores(engine: Engine, values: dict[str, Headline], case_id: str) -> str:
    """Cards grouped by role, with the reason written out when a role cannot be measured with this source."""
    roles = engine.catalog.cases[case_id]["indicadores"]
    ids = [k for r in ROL_TEXTO for k in roles.get(r, [])]
    out = [
        "Cada tarjeta dice su papel: **Resultado** (" + ROL_AYUDA["resultado"] + "), **Adelantado** ("
        + ROL_AYUDA["adelantados"] + ") y **Contrapeso** (" + ROL_AYUDA["contrapeso"] + ").\n\n"
    ]  # fmt: skip
    out.append(tiles(engine, values, ids))
    for rol, texto in (roles.get("pendientes") or {}).items():
        out.append(f"- **{ROL_TEXTO[rol]} que falta medir.** {texto}\n")
    return "".join(out) + "\n"


def resultado_observado(case_id: str, cuerpo: str) -> str:
    ev = load().cases[case_id]["evento"]
    links = " · ".join(f'<a href="{u}">{html.escape(u.split("/")[2])}</a>' for u in ev["fuentes"])
    body = "\n".join("    " + line if line else "" for line in cuerpo.strip().splitlines())
    return (
        f'!!! success "{OBSERVADO}"\n'
        f"    **Evento documentado ({ev['grupo']}, {_fecha_iso(ev['fecha'])}).** {ev['texto']} Fuentes: {links}.\n\n"
        f"{body}\n\n"
        "    *Coincidir en el tiempo no prueba que una sola medida lo causó: el texto dice «coincide con», no «se debe a».*\n\n"
    )


def resultado_estimado(cuerpo: str, motivo: str = "") -> str:
    body = "\n".join("    " + line if line else "" for line in cuerpo.strip().splitlines())
    extra = f"    {motivo}\n\n" if motivo else ""
    return f'!!! note "{ESTIMADO}"\n{extra}{body}\n\n'


def _fecha_iso(s: str) -> str:
    from .current import fecha

    return fecha(s)


def pagina(
    case_id: str, engine: Engine, values: dict[str, Headline], manifest: dict, *, titulo: str, aviso: str,
    en30: tuple[str, str, str], problema: str, pregunta_negocio: str, analisis: str, solucion: str,
    resultado: str, tecnico: str,
) -> str:  # fmt: skip
    return "".join(
        [
            f"# {titulo}\n\n",
            ficha(case_id, manifest),
            aviso,
            en_30_segundos(*en30),
            "## Problema\n\n", problema.strip() + "\n\n",
            "### La pregunta del negocio\n\n", pregunta(pregunta_negocio),
            "## Indicadores\n\n", indicadores(engine, values, case_id),
            "## Análisis\n\n", analisis.strip() + "\n\n",
            "## Solución\n\n", solucion.strip() + "\n\n",
            "## Resultado\n\n", resultado.strip() + "\n\n",
            detalle_tecnico(tecnico),
        ]
    )  # fmt: skip
