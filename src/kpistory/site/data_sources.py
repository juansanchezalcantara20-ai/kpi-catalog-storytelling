"""Página «Fuentes de datos», generada desde data/processed/manifest.json y config/fuentes.yaml."""

from __future__ import annotations

from ..data.solicitudes311 import config
from .common import detalle_tecnico
from .current import fecha

TIPO = {
    "real": "Pública real",
    "referencia": "Pública de referencia (sintética según su publicador)",
    "simulado": "Simulada",
}


def _origen(manifest: dict, key: str) -> tuple[str, str, str]:
    """(origen en esta versión, fecha de descarga, filas) for a config/fuentes.yaml key."""
    from .plantilla import MANIFEST_KEY

    m = manifest.get(MANIFEST_KEY.get(key, key), {})
    tables = manifest.get("tables", {})
    rows = m.get("rows") or {"mantenimiento": tables.get("landing_process_data"), "ventas": tables.get("landing_transactions"),
                             "creditos": tables.get("creditos")}.get(key)  # fmt: skip
    if m.get("origin") == "real":
        return (
            "🟢 Descargada",
            fecha(m["downloaded_at"]),
            f"{rows:,}".replace(",", " ") if rows else "–",
        )
    detalle = (
        "Simulada a propósito"
        if key == "creditos"
        else (
            "Plan B: la descarga falló"
            if "falló" in m.get("note", "")
            else "Plan B: datos simulados"
        )
    )
    return detalle, "–", f"{rows:,}".replace(",", " ") if rows else "–"


def page(manifest: dict) -> str:
    from ..catalog import load, rubros_config
    from ..data.sectores import fuentes

    cfg_r = rubros_config()["rubros"]
    cat = load()
    fs = fuentes()
    md = [
        "# Fuentes de datos\n",
        "Esta página se genera en cada actualización desde el archivo de configuración de fuentes y el registro de la última descarga. Las fuentes "
        "públicas se descargan en GitHub Actions, sin cuenta ni clave; si una descarga falla, ese caso vuelve a datos simulados con "
        "semilla fija y lo dice en su página. Nunca se mezclan datos reales y simulados sin avisarlo.\n",
        "| Fuente | Publicador | Licencia | Rubros | Tipo | En esta versión | Descargada | Filas | Filtros |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for key, f in fs.items():
        if key == "descartadas" or not isinstance(f, dict) or "tipo" not in f:
            continue
        origen, cuando, filas = _origen(manifest, key)
        name = f"[{f['nombre']}]({f['pagina']})" if f.get("pagina") else f["nombre"]
        rub = ", ".join(f"[{cfg_r[r]['nombre']}](rubros/{r}.md)" for r in f["rubros"])
        filtros = f.get("filtros") or (
            f"Departamento de Transporte, últimos {f['periodo']['meses']} meses completos"
            if key == "solicitudes"
            else "–"
        )
        md.append(
            f"| {name} | {f['publicador']} | {f['licencia']} | {rub} | {TIPO[f['tipo']]} | {origen} | {cuando} | {filas} | {filtros} |"
        )
    md.append(
        "\nLos datos simulados muestran el método; no describen una empresa real. Cada generador usa una semilla fija, así que siempre "
        "produce los mismos números. Las comparaciones son entre grupos (países, regiones, niveles, tipos de entidad), nunca entre empresas.\n"
    )
    md.append("## Rubro por rubro\n")
    md.append("| Rubro | Casos | Fuente principal |")
    md.append("|---|---|---|")
    for rid, r in cfg_r.items():
        casos = cat.cases_for_rubro(rid)
        keys = sorted({k for c in casos for k in cat.cases[c]["fuentes"]}, key=list(fs).index)
        src = "; ".join(f"{fs[k]['nombre']} ({TIPO[fs[k]['tipo']].lower()})" for k in keys)
        md.append(
            f"| [{r['nombre']}](rubros/{rid}.md) | "
            + ", ".join(f"[{cat.cases[c]['title']}](cases/{c}.md)" for c in casos)
            + f" | {src} |"
        )
    md.append("\n## Fuentes que se evaluaron y no se usaron\n")
    md.append("| Fuente | Rubros | Por qué no |")
    md.append("|---|---|---|")
    for d in fs.get("descartadas", []):
        md.append(
            f"| {d['fuente']} | {', '.join(cfg_r[r]['nombre'] for r in d['rubros'])} | {d['motivo']} |"
        )
    md.append("")

    cfg = config()
    t = manifest["tickets"]
    md.append("## Atención de solicitudes · Nueva York (servicio 311)\n")
    md.append(
        f"**Fuente:** [{cfg['nombre']}]({cfg['pagina']}), publicada por {cfg['publicador']}. Se descarga por su interfaz "
        "pública, sin cuenta ni clave. **Filtro:** solo el Departamento de Transporte y los últimos "
        f"{cfg['periodo']['meses']} meses completos. **Privacidad:** solo se descargan número de solicitud, fechas, "
        "agencia, tipo de reclamo, canal, estado y distrito; nunca direcciones, coordenadas, nombres ni textos escritos "
        "por los ciudadanos, y el sitio solo publica cifras agregadas.\n"
    )
    if t["origin"] == "real":
        md.append(
            f"En esta versión se descargaron {t.get('rows', 'las')} solicitudes ({t.get('filter', '')}).\n"
        )
    md.append(
        "**Supuesto propio, no una regla oficial de la ciudad:** la ciudad no publica plazos de atención por tipo de "
        "reclamo, así que este proyecto asigna una prioridad y un plazo a cada tipo para poder medir el cumplimiento:\n"
    )
    plazos = cfg["plazos_por_prioridad_horas"]
    md.append(
        "| Tipo de reclamo (como lo publica la ciudad) | Cómo se muestra | Prioridad | Plazo |"
    )
    md.append("|---|---|---|---|")
    for tipo, v in cfg["tipos"].items():
        h = plazos[v["prioridad"]]
        md.append(
            f"| {tipo} | {v['etiqueta']} | {v['prioridad']} | {h // 24 if h >= 48 else h} {'días' if h >= 48 else 'horas'} |"
        )
    d = cfg["tipo_por_defecto"]
    md.append(
        f"| cualquier otro tipo | {d['etiqueta']} | {d['prioridad']} | {plazos[d['prioridad']] // 24} días |"
    )
    md.append(
        "\nLa fuente no registra la primera respuesta, los contactos ni las reaperturas: esos tres indicadores aparecen "
        "como «Sin dato» cuando el caso usa datos reales. Las solicitudes cerradas después de la fecha de corte se cuentan "
        "como abiertas a esa fecha.\n"
    )
    md.append("## Notas sobre las demás fuentes\n")
    md.append(
        "- **Mantenimiento (AI4I 2020):** su publicador lo describe como un conjunto sintético que refleja datos reales de mantenimiento "
        "predictivo; aquí se usa como referencia pública y se cuenta como dato simulado. Las órdenes de trabajo se simulan a partir de sus fallas.\n"
        "- **Inventario y clientes (Online Retail II):** el inventario, el pronóstico, las entregas y la encuesta son simulados: no existe una fuente pública con esos datos para la misma tienda.\n"
        "- **Telecomunicaciones:** la fuente no trae población de 2014 a 2017; se extiende con el crecimiento de los cinco años anteriores de cada país.\n"
        "- **Logística:** la muestra de vuelos no tiene fecha ni aerolínea, así que no permite un antes y un después.\n"
        "- **Calidad de los datos:** se mide sobre los datos de los otros casos tal como llegan.\n"
        "- No se usa ningún dato de empleadores, clientes ni personas reales; solo se publican cifras agregadas.\n"
    )
    md.append(f"\nVersión generada el {fecha(manifest['generated_at'][:10])}.\n")
    tech = [f"- Modo de origen de esta versión: `{manifest['source_mode']}`."]
    tech += [
        f"- `{k}`: {manifest[k]['origin']} - {manifest[k]['note']}"
        for k in (
            "tickets",
            "process_data",
            "work_orders",
            "transactions",
            "inventory",
            "survey",
            "energia",
            "salud",
            "moviles",
            "docentes",
            "vuelos",
            "creditos",
        )
    ]
    tech.append(
        "- Configuración de las fuentes: `config/fuentes.yaml`; registro de la última descarga: `data/processed/manifest.json`."
    )
    md.append(detalle_tecnico("\n".join(tech)))
    return "\n".join(md)
