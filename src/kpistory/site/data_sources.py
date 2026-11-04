"""Página «Fuentes de datos», generada desde data/processed/manifest.json y config/fuentes.yaml."""

from __future__ import annotations

from ..data.solicitudes311 import config
from .common import detalle_tecnico
from .current import fecha

CASOS = {
    "tickets": "Caso 1 · Atención de solicitudes",
    "process_data": "Caso 2 · Mantenimiento",
    "work_orders": "Caso 2 · Mantenimiento",
    "transactions": "Casos 3 y 4 · Inventario y clientes",
    "inventory": "Caso 3 · Inventario",
    "survey": "Caso 4 · Clientes",
}


def page(manifest: dict) -> str:
    md = [
        "# Fuentes de datos\n",
        "Esta página se genera en cada actualización. Las fuentes públicas se descargan en GitHub Actions; si una descarga "
        "falla, el sitio vuelve a los datos simulados de esa fuente y lo dice en la página del caso. Nunca se mezclan "
        "datos reales y simulados sin avisarlo.\n",
        "| Datos | Se usan en | Origen en esta versión | Detalle |",
        "|---|---|---|---|",
    ]
    for key in ("tickets", "process_data", "work_orders", "transactions", "inventory", "survey"):
        m = manifest[key]
        real = m["origin"] == "real"
        origen = (
            f"🟢 Datos reales, descargados el {fecha(m['downloaded_at'])}"
            if real
            else "Datos simulados"
        )
        name = f"[{m['name']}]({m['url']})" if m.get("url") else m["name"]
        detalle = (
            (f"{m['rows']} filas" if real and m.get("rows") else "descarga correcta")
            if real
            else (
                "la descarga falló; se usa el plan B"
                if "falló" in m["note"]
                else "simulación con reglas explícitas"
            )
        )
        md.append(f"| {name} | {CASOS[key]} | {origen} | {detalle} |")
    md.append(
        "\nLos datos simulados muestran el método; no describen una empresa real. Cada generador usa una semilla fija, así que siempre produce los mismos números.\n"
    )

    cfg = config()
    t = manifest["tickets"]
    md.append("## Caso 1 · Solicitudes ciudadanas de Nueva York (servicio 311)\n")
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
    md.append("## Casos 2 a 5\n")
    md.append(
        "- **Mantenimiento:** datos de proceso de máquinas [AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) "
        "(repositorio UCI, licencia CC BY 4.0). Las órdenes de trabajo son simuladas a partir de sus fallas.\n"
        "- **Inventario y clientes:** ventas de [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) "
        "(repositorio UCI, CC BY 4.0). El inventario, el pronóstico, las entregas y la encuesta de recomendación son simulados: "
        "no existe una fuente pública con esos datos para la misma tienda.\n"
        "- **Calidad de los datos:** se mide sobre los datos de los casos 1 a 4 tal como llegan.\n"
        "- No se usa ningún dato de empleadores, clientes ni personas reales.\n"
    )
    md.append(f"\nVersión generada el {fecha(manifest['generated_at'][:10])}.\n")
    tech = [f"- Modo de origen de esta versión: `{manifest['source_mode']}`."]
    tech += [
        f"- `{k}`: {manifest[k]['origin']} - {manifest[k]['note']}"
        for k in ("tickets", "process_data", "work_orders", "transactions", "inventory", "survey")
    ]
    tech.append(
        "- Configuración de las fuentes: `config/fuentes.yaml`; registro de la última descarga: `data/processed/manifest.json`."
    )
    md.append(detalle_tecnico("\n".join(tech)))
    return "\n".join(md)
