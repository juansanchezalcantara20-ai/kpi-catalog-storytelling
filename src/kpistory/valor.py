"""Business value: translate each case's gap to target into soles and hours per month.

Assumptions live in config/supuestos_valor.yaml (all illustrative). For each case:
  * the gap between the reference value and the target of its driver KPIs;
  * the units affected ("151 pendientes antiguas de más");
  * the monthly and annual cost in S/ and the monthly hours;
  * a transparent "decision -> result" scenario: the monthly series of the main KPI,
    projected 6 months with and without the decision, the value captured and a
    bootstrap interval that answers "¿es ruido?".
Every page (home, management summary, cases, dashboard) reads `valores()`, so the
numbers can never disagree (tested).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd
import yaml

from .engine import Engine
from .formulas.customers import rfm_table
from .formulas.data_quality import completeness_counts
from .paths import ROOT
from .site.current import Headline, headline, mes

CONFIG_PATH = ROOT / "config" / "supuestos_valor.yaml"
CASE_TITLES = {
    "service": "Atención de solicitudes",
    "maintenance": "Mantenimiento",
    "inventory": "Inventario",
    "customers": "Clientes",
    "data_quality": "Calidad de los datos",
}
SEED = 2026
HORIZON = 6  # months projected after the decision


@lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@dataclass
class Componente:
    kpi: str
    nombre: str
    valor: float
    meta: float
    direccion: str
    unidad_pct: bool
    base: float
    base_texto: str
    unidad: str
    costo_unitario: float
    horas_unitarias: float
    brecha: float
    unidades_de_mas: float
    soles_mes: float
    horas_mes: float
    explicacion_costo: str
    explicacion_horas: str
    ilustrativo: bool


@dataclass
class Escenario:
    meses_historia: list[str]
    meses: list[str]
    historia: list[float]
    sin_decision: list[float]
    con_decision: list[float]
    fecha_decision: str
    efecto: float
    explicacion: str
    valor_capturado: float
    mejora: float
    intervalo: tuple[float, float]
    es_ruido: bool


@dataclass
class ValorCaso:
    caso: str
    titulo: str
    componentes: list[Componente]
    soles_mes: float
    soles_anio: float
    horas_mes: float
    resumen_brecha: str
    accion: str = ""
    responsable: str = ""
    fecha: str = ""
    escenario: Escenario | None = None
    notas: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def gap(value: float, target: float, direction: str) -> float:
    """Distance to target in the 'bad' direction, never negative."""
    if value is None or math.isnan(value):
        return 0.0
    if direction == "lower_is_better":
        return max(0.0, value - target)
    return max(0.0, target - value)


def _bases(
    t: dict[str, pd.DataFrame], H: dict[str, Headline], e: Engine
) -> dict[str, tuple[float, str]]:
    fx = config()["tipo_cambio_gbp"]["valor"]
    tk = t["tickets"]
    res = tk[tk["status"].eq("resolved")]
    q = res["resolved_at"].dt.to_period("Q").max()
    if res["resolved_at"].max() < q.end_time.normalize():
        q -= 1
    resolved_q = res[res["resolved_at"].dt.to_period("Q").eq(q)]
    ap = t["asset_periods"]
    months = ap["month"].nunique() or 1
    ol = t["order_lines"]
    end = t["inventory_daily"]["date"].max()
    ol12 = ol[ol["order_date"] > end - pd.Timedelta(days=365)]
    trx = t["landing_transactions"]
    span = max(1, round((trx["InvoiceDate"].max() - trx["InvoiceDate"].min()).days / 30.4))
    return {
        "solicitudes_abiertas": (
            float(tk["status"].eq("open").sum()),
            "solicitudes abiertas a la fecha de corte",
        ),
        "solicitudes_cerradas_mes": (len(resolved_q) / 3, "solicitudes cerradas al mes"),
        "horas_programadas_mes": (
            float(ap["scheduled_hours"].sum()) / months,
            "horas programadas al mes en la flota",
        ),
        "pedidos_mes": (ol12["order_id"].nunique() / 12, "pedidos al mes"),
        "valor_inventario_soles": (
            float(t["inventory_snapshot"]["on_hand_value"].sum()) * fx,
            "soles de inventario a costo",
        ),
        "ingreso_mes_soles": (
            float(t["customer_rfm"]["monetary"].sum()) * fx / 12,
            "soles de ingreso al mes de clientes identificados",
        ),
        "registros_ventas_mes": (len(trx) / span, "registros de venta al mes"),
    }


def _driver_value(kid: str, t: dict, H: dict[str, Headline]) -> float:
    if kid == "dq_completeness":  # the value case is about the sales records, where the gap is
        dq = t["dq_results"]
        row = dq[(dq["dataset"] == "transactions") & (dq["dimension"] == "completeness")]
        return float(row["value"].iloc[0])
    return H[kid].value


def monthly_series(caso: str, t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> pd.Series:
    """Last 12 monthly values of the case's main KPI (used by the decision scenario)."""
    if caso == "service":
        tk = t["tickets"]
        snap = pd.Timestamp(manifest["tickets"]["snapshot"])
        ends = pd.date_range(end=snap.normalize(), periods=12, freq="ME") + pd.Timedelta(
            hours=23, minutes=59
        )
        vals = {}
        for m in ends:
            open_ = tk[
                (tk["created_at"] <= m) & (tk["resolved_at"].isna() | (tk["resolved_at"] > m))
            ]
            age = (m - open_["created_at"]).dt.total_seconds() / 86400
            vals[m.to_period("M").start_time] = float((age > 7).mean()) if len(open_) else math.nan
        return pd.Series(vals)
    if caso == "maintenance":
        s = e.compute_by("availability", t["asset_periods"], "month").set_index("month")["value"]
        return s.tail(12)
    if caso == "inventory":
        ol = t["order_lines"]
        end = t["inventory_daily"]["date"].max()
        ol = ol.assign(m=ol["order_date"].dt.to_period("M").dt.start_time)
        ol = (
            ol[ol["m"] < end.to_period("M").start_time]
            if end < end + pd.offsets.MonthEnd(0)
            else ol
        )
        return e.compute_by("otif", ol, "m").set_index("m")["value"].tail(12)
    if caso == "customers":
        cs = t["customer_sales"]
        last = cs["invoice_date"].max().normalize()
        vals = {}
        for m in pd.date_range(end=last, periods=12, freq="ME"):
            rfm = rfm_table(cs, snapshot=m + pd.Timedelta(days=1), window_days=365)
            vals[m.to_period("M").start_time] = e.compute("revenue_at_risk_share", rfm)
        return pd.Series(vals)
    trx = t["landing_transactions"]
    cols = ["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"]
    m = trx["InvoiceDate"].dt.to_period("M").dt.start_time
    s = pd.Series(
        {k: (lambda p, q: p / q)(*completeness_counts(g, cols)) for k, g in trx.groupby(m)}
    )
    last = trx["InvoiceDate"].max()
    if last < last + pd.offsets.MonthEnd(0):
        s = s.iloc[:-1]
    return s.tail(12)


def escenario(
    caso: str, comp: Componente, serie: pd.Series, efecto: float, explicacion: str
) -> Escenario:
    """Transparent simulation: 6 months after the decision, with and without it."""
    rng = np.random.default_rng(SEED + len(caso))
    hist = serie.dropna()
    noise = float(hist.diff().std() or 0.01) * 0.3
    level = float(hist.tail(3).mean())
    sign = 1 if comp.direccion == "lower_is_better" else -1  # direction in which 'worse' grows
    gap_now = gap(level, comp.meta, comp.direccion)
    sin = level + rng.normal(0, noise, HORIZON)
    ramp = np.minimum(np.arange(1, HORIZON + 1) / 3, 1.0)
    con = level - sign * gap_now * efecto * ramp + rng.normal(0, noise, HORIZON)
    if comp.unidad_pct:
        sin, con = np.clip(sin, 0, 1), np.clip(con, 0, 1)
    start = hist.index[-1] + pd.offsets.MonthBegin(1)
    meses = [mes(d) for d in pd.date_range(start, periods=HORIZON, freq="MS")]
    # value captured over the horizon: difference in monthly cost between the two scenarios
    cost = lambda v: comp.base * gap(v, comp.meta, comp.direccion) * comp.costo_unitario  # noqa: E731
    captured = float(sum(cost(a) - cost(b) for a, b in zip(sin, con, strict=True)))
    # before (last 6 real months) vs after (months 4-6 with the decision): bootstrap interval of the change
    before, after = hist.tail(6).to_numpy(), con[3:]
    boots = [
        rng.choice(after, len(after)).mean() - rng.choice(before, len(before)).mean()
        for _ in range(2000)
    ]
    lo, hi = np.percentile(boots, [5, 95])
    change = float(after.mean() - before.mean())
    return Escenario(
        meses_historia=[mes(d) for d in hist.index], meses=meses, historia=[float(v) for v in hist.to_numpy()], sin_decision=[float(v) for v in sin],
        con_decision=[float(v) for v in con], fecha_decision=mes(start), efecto=efecto, explicacion=explicacion,
        valor_capturado=max(0.0, captured), mejora=change, intervalo=(float(lo), float(hi)),
        es_ruido=bool(lo <= 0 <= hi),
    )  # fmt: skip


def _money(x: float) -> str:
    return f"S/ {x:,.0f}".replace(",", " ")


def _units(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def valores(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> dict[str, ValorCaso]:
    cfg = config()
    H = headline(t, e, manifest)
    bases = _bases(t, H, e)
    out: dict[str, ValorCaso] = {}
    for caso, spec in cfg["casos"].items():
        comps = []
        for c in spec["componentes"]:
            k = e.catalog[c["indicador"]]
            value = _driver_value(k.id, t, H)
            base, base_txt = bases[c["base"]]
            g = gap(value, k.target, k.direction)
            extra = base * g
            comps.append(Componente(
                kpi=k.id, nombre=k.name if k.id != "dq_completeness" else "Completitud de las ventas", valor=value,
                meta=k.target, direccion=k.direction, unidad_pct=k.unit == "percent", base=base, base_texto=base_txt,
                unidad=c["unidad"], costo_unitario=float(c["costo_unitario"]), horas_unitarias=float(c["horas_unitarias"]),
                brecha=g, unidades_de_mas=extra, soles_mes=extra * c["costo_unitario"], horas_mes=extra * c["horas_unitarias"],
                explicacion_costo=c["explicacion_costo"], explicacion_horas=c["explicacion_horas"], ilustrativo=bool(c.get("ilustrativo")),
            ))  # fmt: skip
        main = comps[0]
        soles = sum(c.soles_mes for c in comps)
        horas = sum(c.horas_mes for c in comps)
        if soles > 0:
            resumen = (
                f"{_units(main.unidades_de_mas)} {main.unidad} por encima de lo que permite la meta"
            )
        else:
            resumen = "En meta: no hay brecha que cueste dinero en este momento"
        from .site.current import fecha

        hoy = pd.Timestamp(manifest.get("generated_at", "2026-01-01")[:10])
        v = ValorCaso(caso=caso, titulo=CASE_TITLES[caso], componentes=comps, soles_mes=soles, soles_anio=soles * 12,
                      horas_mes=horas, resumen_brecha=resumen, accion=spec["accion"], responsable=spec["responsable"],
                      fecha=fecha(hoy + pd.Timedelta(days=int(spec["plazo_dias"]))))  # fmt: skip
        serie = monthly_series(caso, t, e, manifest)
        if len(serie.dropna()) >= 4:
            v.escenario = escenario(
                caso, main, serie, float(spec["efecto_decision"]), spec["explicacion_efecto"]
            )
        out[caso] = v
    return out


def money(x: float) -> str:
    return _money(x)


def units(x: float) -> str:
    return _units(x)


_CACHE: dict[str, dict[str, ValorCaso]] = {}


def get_valores(t: dict[str, pd.DataFrame], e: Engine, manifest: dict) -> dict[str, ValorCaso]:
    """valores() computed once per data build (the pages, the summary and the dashboard share it)."""
    key = manifest.get("generated_at", "") + str(len(t["tickets"]))
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = valores(t, e, manifest)
    return _CACHE[key]


def top_alertas(vals: dict[str, ValorCaso], n: int = 3) -> list[ValorCaso]:
    return sorted((v for v in vals.values() if v.soles_mes > 0), key=lambda v: -v.soles_anio)[:n]


def total_anio(vals: dict[str, ValorCaso]) -> float:
    return sum(v.soles_anio for v in vals.values())
