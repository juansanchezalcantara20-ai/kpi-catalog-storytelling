# Casos

Cada caso se cuenta en el sitio con la misma plantilla **Problema → Solución → Resultado**, en siete partes:
**En 30 segundos → Problema → Indicadores (resultado, adelantados y contrapeso) → Análisis → Solución → Resultado →
Detalle técnico**. El resultado dice siempre si es **observado en datos reales** (solo con un evento documentado y su
fuente) o **estimado (escenario)**. Una prueba revisa las siete partes y la etiqueta en cada página publicada.

| Caso | Rubro | Datos | Resultado | Plan B (si la descarga falla) |
|------|-------|-------|-----------|------|
| [Atención de solicitudes](01_service/README.md) | Servicios y atención | **Reales:** NYC 311, Departamento de Transporte | estimado | mesa de ayuda simulada |
| [Mantenimiento](02_maintenance/README.md) | Minería | AI4I 2020 (UCI): conjunto de referencia, sintético según su publicador | estimado | AI4I regenerado con sus reglas publicadas |
| [Inventario y demanda](03_inventory/README.md) | Retail | **Reales:** Online Retail II (UCI) + inventario simulado | estimado | ventas simuladas con la misma estructura |
| [Clientes](04_customers/README.md) | Retail | **Reales:** Online Retail II (UCI) + encuesta simulada | estimado | las mismas ventas simuladas |
| [Calidad de los datos](05_data_quality/README.md) | Retail, Minería, Servicios | los datos de los casos anteriores tal como llegan | estimado | sigue a los otros casos |
| Morosidad de créditos | Banca, seguros y AFP | **Simulados** (no hay una fuente pública estable sin registro) | estimado | – |
| Generación eléctrica | Energía | **Reales:** Our World in Data, energía (CC BY 4.0) | **observado**: retiro del carbón en Chile (2019) | generación simulada |
| Vacunación y mortalidad | Salud | **Reales:** Our World in Data, COVID-19 (CC BY 4.0) | **observado**: inicio de la vacunación en Perú (9 feb 2021) | series simuladas |
| Líneas móviles | Telecomunicaciones | **Reales:** UIT vía Our World in Data (TidyTuesday) | estimado | penetración simulada |
| Alumnos por docente | Educación | **Reales:** UNESCO (TidyTuesday) | estimado | relaciones simuladas |
| Puntualidad en el transporte | Logística y transporte | **Reales:** Oficina de Estadísticas de Transporte de EE. UU. (vega-datasets) | estimado | vuelos simulados |

Si una descarga falla, el caso usa su plan B y su resultado pasa a «estimado» aunque el catálogo lo declare
«observado»: un resultado observado exige datos reales en esa versión. URL, licencia, publicador, filtros y filas de
cada fuente están en `config/fuentes.yaml` y en la página *Fuentes* del sitio.
