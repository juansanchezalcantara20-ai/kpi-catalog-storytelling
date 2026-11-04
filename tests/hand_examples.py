"""Hand-calculated examples: one small table per KPI with the expected result written out.

Each example is computed by hand in its `working` string, so a reader can check
the arithmetic without running anything. The same examples are used by
test_formulas.py (Python engine) and test_sql.py (reference SQL), and they are
shown on the KPI pages of the site as "worked example from the test suite".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

T = pd.Timestamp


@dataclass
class HandExample:
    kpi_id: str
    table: pd.DataFrame
    expected: float
    working: str
    overrides: dict[str, Any] = field(default_factory=dict)


def _tickets() -> pd.DataFrame:
    # Five tickets. Hours are already derived (see derive_ticket_columns tests).
    return pd.DataFrame(
        {
            "ticket_id": [1, 2, 3, 4, 5],
            "status": ["resolved", "resolved", "resolved", "resolved", "open"],
            "first_response_hours": [1.0, 3.0, 0.5, 6.0, None],
            "resolution_hours": [10.0, 30.0, 4.0, 50.0, None],
            "sla_target_hours": [24.0, 24.0, 8.0, 72.0, 24.0],
            "contacts": [1, 2, 1, 1, 1],
            "reopened": [False, False, True, False, False],
            "age_days": [None, None, None, None, 9.0],
        }
    )


def _backlog() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "status": ["open", "open", "open", "open", "resolved"],
            "age_days": [2.0, 8.0, 15.0, 7.0, None],
        }
    )


EXAMPLES: list[HandExample] = [
    # ---------------------------------------------------------------- service
    HandExample(
        "first_response_time",
        _tickets(),
        2.0,
        "Cuatro solicitudes respondidas esperaron 0.5, 1, 3 y 6 horas (la quinta todavía no tiene respuesta). La del medio entre 4 valores es (1 + 3) / 2 = 2.0 horas.",
    ),
    HandExample(
        "resolution_time",
        _tickets(),
        20.0,
        "Cuatro solicitudes cerradas tardaron 4, 10, 30 y 50 horas. La del medio es (10 + 30) / 2 = 20.0 horas. El promedio sería 23.5 horas, inflado por la de 50.",
    ),
    HandExample(
        "sla_compliance",
        _tickets(),
        0.75,
        "Cuatro solicitudes cerradas con plazos de 24, 24, 8 y 72 horas tardaron 10, 30, 4 y 50 horas. Tres cumplieron su plazo: 3 de 4 = 75 %. La solicitud abierta no cuenta.",
    ),
    HandExample(
        "backlog_aged_share",
        _backlog(),
        0.5,
        "Hay cuatro solicitudes abiertas con 2, 8, 15 y 7 días. Llevan más de 7 días las de 8 y 15 (la de 7 exactos no). 2 de 4 = 50 %.",
    ),
    HandExample(
        "first_contact_resolution",
        _tickets(),
        0.5,
        "De cuatro solicitudes cerradas, dos se resolvieron con un solo contacto y sin reabrirse; una necesitó dos contactos y otra se reabrió. 2 de 4 = 50 %.",
    ),
    HandExample(
        "reopen_rate",
        _tickets(),
        0.25,
        "De cuatro solicitudes cerradas, una se reabrió: 1 de 4 = 25 %.",
    ),
    # ------------------------------------------------------------ maintenance
    HandExample(
        "mtbf",
        pd.DataFrame(
            {
                "asset_id": ["A", "A", "B"],
                "operating_hours": [400.0, 300.0, 500.0],
                "failures": [2, 0, 1],
            }
        ),
        400.0,
        "Dos máquinas operaron 400 + 300 + 500 = 1 200 horas y tuvieron 2 + 0 + 1 = 3 fallas: 1 200 / 3 = 400 horas entre fallas. Promediar mes por mes fallaría en el mes sin fallas.",
    ),
    HandExample(
        "mttr",
        pd.DataFrame(
            {
                "wo_type": ["corrective", "corrective", "corrective", "preventive"],
                "repair_hours": [2.0, 3.0, 10.0, 1.0],
            }
        ),
        5.0,
        "Tres reparaciones duraron 2, 3 y 10 horas: (2 + 3 + 10) / 3 = 5.0 horas en promedio. La reparación típica es de 3 horas: una sola reparación larga mueve el promedio.",
    ),
    HandExample(
        "availability",
        pd.DataFrame(
            {
                "scheduled_hours": [160.0, 160.0],
                "unplanned_downtime_hours": [8.0, 0.0],
            }
        ),
        0.975,
        "Dos meses con 160 horas programadas cada uno (320 en total) y 8 horas perdidas por fallas: (320 − 8) / 320 = 97.5 %.",
    ),
    HandExample(
        "pm_compliance",
        pd.DataFrame(
            {
                "wo_type": ["preventive"] * 4 + ["corrective"],
                "due_date": [
                    T("2024-03-01"),
                    T("2024-03-10"),
                    T("2024-03-20"),
                    T("2024-03-25"),
                    T("2024-03-05"),
                ],
                "completed_at": [
                    T("2024-03-01"),
                    T("2024-03-13"),
                    T("2024-03-24"),
                    pd.NaT,
                    T("2024-03-30"),
                ],
            }
        ),
        0.5,
        "Con 3 días de tolerancia: un preventivo se hizo el día programado (a tiempo), otro 3 días después (a tiempo, el límite cuenta), otro 4 días después (tarde) y otro no se hizo (tarde). 2 de 4 = 50 %.",
    ),
    HandExample(
        "planned_work_share",
        pd.DataFrame({"planned": [True, True, False], "labor_hours": [4.0, 2.0, 6.0]}),
        0.5,
        "Hubo 4 + 2 = 6 horas de trabajo planificado de 12 horas en total: 50 %. Contando órdenes en vez de horas saldría 2 de 3.",
    ),
    # -------------------------------------------------------------- inventory
    HandExample(
        "fill_rate",
        pd.DataFrame({"qty_ordered": [10, 5, 5], "qty_shipped": [10, 3, 5]}),
        0.9,
        "Se pidieron 20 unidades y se despacharon 18: 90 %.",
    ),
    HandExample(
        "otif",
        pd.DataFrame(
            {
                "order_id": [1, 1, 2, 3, 4],
                "qty_ordered": [5, 5, 4, 2, 3],
                "qty_shipped": [5, 5, 4, 1, 3],
                "promised_date": [T("2024-01-10")] * 5,
                "delivered_date": [
                    T("2024-01-09"),
                    T("2024-01-10"),
                    T("2024-01-11"),
                    T("2024-01-10"),
                    T("2024-01-10"),
                ],
            }
        ),
        0.5,
        "Pedido 1: dos líneas completas y a tiempo, bien. Pedido 2: un día tarde, falla. Pedido 3: llegó 1 de 2 unidades, falla. Pedido 4: bien. 2 de 4 pedidos = 50 %. Con los mismos datos, las unidades atendidas son 18 de 19 = 94.7 %: este indicador es más exigente.",
    ),
    HandExample(
        "inventory_turnover",
        pd.DataFrame(
            {
                "date": [T("2024-01-01"), T("2024-01-01"), T("2024-01-02"), T("2024-01-02")],
                "sku": ["a", "b", "a", "b"],
                "on_hand_value": [100.0, 100.0, 50.0, 150.0],
                "cogs_value": [5.0, 5.0, 5.0, 5.0],
            }
        ),
        18.25,
        "En 2 días se vendió a costo 20; llevado a un año: 20 × 365 / 2 = 3 650. El inventario valía 200 cada día, así que el promedio es 200. Rotación = 3 650 / 200 = 18.25 veces al año.",
    ),
    HandExample(
        "days_of_cover",
        pd.DataFrame(
            {
                "date": [T("2024-01-01"), T("2024-01-02"), T("2024-01-03")],
                "on_hand_units": [100, 90, 60],
                "demand_units": [10, 10, 10],
            }
        ),
        6.0,
        "En 3 días se vendieron 30 unidades: 10 por día. El último día quedan 60 unidades: 60 / 10 = 6 días de cobertura.",
    ),
    HandExample(
        "stockout_rate",
        pd.DataFrame(
            {
                "on_hand_units": [0, 5, 3, 0, 10, 2, 0, 1, 0, 0],
                "active": [True] * 8 + [False, False],
            }
        ),
        0.375,
        "De 8 días-producto activos (dos filas más son de un producto descontinuado y no cuentan), 3 terminaron sin inventario: 3 de 8 = 37.5 %. Contando el producto descontinuado saldría 5 de 10.",
    ),
    HandExample(
        "obsolescence_share",
        pd.DataFrame(
            {"on_hand_value": [500.0, 300.0, 200.0], "days_since_last_movement": [10, 200, 181]}
        ),
        0.5,
        "Con un límite de 180 días: dos productos valen 300 y 200 y no se venden hace 200 y 181 días. 500 de un inventario de 1 000 = 50 %.",
    ),
    HandExample(
        "mape",
        pd.DataFrame({"actual_units": [100, 10, 0], "forecast_units": [90, 20, 5]}),
        0.55,
        "Dos productos vendieron 100 y 10 unidades; el pronóstico dijo 90 y 20 (un tercero no vendió y se excluye). Errores: 10 % y 100 %. Promedio = 55 %: el producto pequeño domina.",
    ),
    HandExample(
        "wape",
        pd.DataFrame({"actual_units": [100, 10, 0], "forecast_units": [90, 20, 5]}),
        25 / 110,
        "Con los mismos datos: los errores suman 10 + 10 + 5 = 25 unidades y se vendieron 110. 25 / 110 = 22.7 %, frente al 55 % del error promedio.",
    ),
    HandExample(
        "forecast_bias",
        pd.DataFrame({"actual_units": [100, 10, 0], "forecast_units": [90, 20, 5]}),
        5 / 110,
        "Se pronosticaron 115 unidades y se vendieron 110: (115 − 110) / 110 = +4.5 %, dentro de la franja de ± 5 %.",
    ),
    # -------------------------------------------------------------- customers
    HandExample(
        "retention_rate",
        pd.DataFrame(
            {
                "customer_id": ["a", "b", "c", "d", "a", "c", "e"],
                "invoice_date": [
                    T("2024-01-15"),
                    T("2024-02-01"),
                    T("2024-03-30"),
                    T("2024-03-01"),
                    T("2024-04-02"),
                    T("2024-05-20"),
                    T("2024-06-01"),
                ],
            }
        ),
        0.5,
        "En el primer trimestre compraron a, b, c y d; en el segundo, a, c y e. Volvieron a y c: 2 de 4 = 50 % (e es nuevo y no cuenta).",
    ),
    HandExample(
        "repeat_purchase_rate",
        pd.DataFrame(
            {
                "customer_id": ["a", "a", "a", "b", "b", "c"],
                "invoice_id": ["i1", "i1", "i2", "i3", "i3", "i4"],
            }
        ),
        1 / 3,
        "El cliente a tiene 2 facturas, b tiene 1 (con dos líneas) y c tiene 1. Solo a repitió: 1 de 3 = 33.3 %. Contando líneas en vez de facturas saldría 2 de 3, mal.",
    ),
    HandExample(
        "revenue_at_risk_share",
        pd.DataFrame(
            {
                "segment": ["Campeones", "En riesgo", "En riesgo", "Dormidos"],
                "monetary": [500.0, 200.0, 100.0, 200.0],
            }
        ),
        0.3,
        "Los clientes «en riesgo» compraron 200 + 100 = 300 de un ingreso total de 1 000: 30 %.",
    ),
    HandExample(
        "nps",
        pd.DataFrame({"score": [10, 9, 9, 8, 7, 6, 3, 10, 0, 9]}),
        20.0,
        "Diez respuestas: 5 promotores (9 o 10), 3 detractores (0 a 6) y 2 neutros. 100 × (5 − 3) / 10 = +20. La nota promedio, 7.1, no es este indicador.",
    ),
    # ----------------------------------------------------------- data quality
    HandExample(
        "dq_completeness",
        pd.DataFrame(
            {"id": [1, 2, 3, 4], "customer": ["x", None, "", "y"], "amount": [1.0, 2.0, None, 4.0]}
        ),
        0.625,
        "Dos campos obligatorios en 4 filas = 8 celdas. El cliente falta dos veces (una vacía y otra en blanco) y el monto una vez: 5 de 8 llenas = 62.5 %.",
        overrides={"columns": ["customer", "amount"]},
    ),
    HandExample(
        "dq_uniqueness",
        pd.DataFrame({"ticket_id": [1, 2, 2, 3, 3]}),
        0.6,
        "Cinco filas con las claves 1, 2, 2, 3, 3: hay 3 registros distintos. 3 de 5 = 60 %.",
        overrides={"key": ["ticket_id"]},
    ),
    HandExample(
        "dq_validity",
        pd.DataFrame({"quantity": [5, -1, 3, 0], "price": [2.0, 2.0, -1.0, 1.0]}),
        0.25,
        "Reglas: cantidad mayor que cero y precio no negativo. La fila 1 cumple; la 2 falla la cantidad; la 3, el precio; la 4, la cantidad. 1 de 4 = 25 % (se cuentan filas, no fallas).",
        overrides={"rules": ["quantity > 0", "price >= 0"]},
    ),
    HandExample(
        "dq_timeliness",
        pd.DataFrame(
            {
                "event_at": [T("2024-01-01 08:00")] * 4,
                "loaded_at": [
                    T("2024-01-01 09:00"),
                    T("2024-01-02 08:00"),
                    T("2024-01-02 08:01"),
                    T("2024-01-05"),
                ],
            }
        ),
        0.5,
        "Plazo de 24 horas. Cuatro registros llegaron 1 h, 24 h (justo a tiempo), 24 h y 1 minuto, y 88 h después. 2 de 4 = 50 %.",
        overrides={"event_col": "event_at", "loaded_col": "loaded_at", "max_delay_hours": 24},
    ),
]

BY_ID = {e.kpi_id: e for e in EXAMPLES}
