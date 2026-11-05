"""Sector cases: public datasets compared by group (country, region, entity type), never by company.

Every real loader returns a tidy table with Spanish group labels and a dict with the rows kept
and the filters applied (shown on the Fuentes page). Every source has a seeded synthetic plan B
with the same columns, used when the download fails or in CI (`--source synthetic`).

Sources (all public, no account or API key; URLs and licences in config/fuentes.yaml):
  energia     Our World in Data, energy data (CC BY 4.0)
  vacunas     Our World in Data, COVID-19 vaccinations (CC BY 4.0)
  mortalidad  Our World in Data, COVID-19 confirmed deaths (CC BY 4.0)
  moviles     ITU mobile subscriptions via Our World in Data, TidyTuesday 2020-11-10
  docentes    UNESCO Institute for Statistics via TidyTuesday 2019-05-07
  vuelos      U.S. Bureau of Transportation Statistics via vega-datasets (flights-200k)
  creditos    simulated only: no stable public loan-level source without registration
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd
import yaml

from ..paths import ROOT
from .download import DownloadError, fetch

SUDAMERICA = {
    "Argentina": "Argentina", "Bolivia": "Bolivia", "Brazil": "Brasil", "Chile": "Chile",
    "Colombia": "Colombia", "Ecuador": "Ecuador", "Paraguay": "Paraguay", "Peru": "Perú",
    "Uruguay": "Uruguay", "Venezuela": "Venezuela",
}  # fmt: skip
SEED = 2026


@lru_cache(maxsize=1)
def fuentes() -> dict:
    with open(ROOT / "config" / "fuentes.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _check_rows(df: pd.DataFrame, key: str) -> pd.DataFrame:
    minimo = fuentes()[key].get("minimo_filas", 1)
    if len(df) < minimo:
        raise DownloadError(f"solo quedaron {len(df)} filas (mínimo esperado: {minimo})")
    return df


# ------------------------------------------------------------------ energía
def energia_real() -> tuple[pd.DataFrame, dict]:
    cfg = fuentes()["energia"]
    raw = pd.read_csv(fetch(cfg["descarga"], "owid-energy-data.csv"))
    d = raw[raw["country"].isin(SUDAMERICA) & (raw["year"] >= cfg["desde"])].copy()
    d = d.dropna(subset=["electricity_generation"])
    out = pd.DataFrame(
        {
            "country": d["country"].map(SUDAMERICA),
            "year": d["year"].astype(int),
            "generation_twh": d["electricity_generation"],
            "renewables_twh": d["renewables_electricity"],
            "fossil_twh": d["fossil_electricity"],
            "coal_twh": d["coal_electricity"],
            "carbon_intensity": d["carbon_intensity_elec"],
        }
    )
    out = _check_rows(out.reset_index(drop=True), "energia")
    return out, {"rows": len(out), "filter": f"10 países de Sudamérica, desde {cfg['desde']}"}


def energia_sintetica(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i, c in enumerate(SUDAMERICA.values()):
        gen0, ren0 = rng.uniform(10, 120), rng.uniform(0.3, 0.8)
        for y in range(2000, 2025):
            t = y - 2000
            gen = gen0 * (1.03**t) * rng.normal(1, 0.02)
            ren = float(
                np.clip(
                    ren0
                    + 0.004 * t
                    + rng.normal(0, 0.03)
                    + (0.012 * (y - 2019) if c == "Chile" and y > 2019 else 0),
                    0.05,
                    0.98,
                )
            )
            coal = float(
                np.clip(
                    (0.35 if c == "Chile" else 0.03)
                    - (0.035 * (y - 2019) if c == "Chile" and y > 2019 else 0),
                    0,
                    1,
                )
            ) * (1 - ren)
            fossil = 1 - ren
            rows.append({"country": c, "year": y, "generation_twh": gen, "renewables_twh": gen * ren, "fossil_twh": gen * fossil,
                         "coal_twh": gen * min(coal, fossil), "carbon_intensity": 50 + 700 * fossil * (0.6 + 0.4 * (i % 3) / 2)})  # fmt: skip
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ salud
def salud_real() -> tuple[pd.DataFrame, dict]:
    cfg_v, cfg_m = fuentes()["vacunas"], fuentes()["mortalidad"]
    vac = pd.read_csv(fetch(cfg_v["descarga"], "owid-vaccinations.csv"), parse_dates=["date"])
    vac = vac[vac["location"].isin(SUDAMERICA)]
    ok = vac["people_fully_vaccinated"].gt(0) & vac["people_fully_vaccinated_per_hundred"].gt(0)
    pop = (
        (
            vac.loc[ok, "people_fully_vaccinated"]
            * 100
            / vac.loc[ok, "people_fully_vaccinated_per_hundred"]
        )
        .groupby(vac.loc[ok, "location"])
        .median()
    )
    wide = pd.read_csv(
        fetch(cfg_m["descarga"], "owid-weekly-deaths-per-million.csv"), parse_dates=["date"]
    )
    cols = [c for c in SUDAMERICA if c in wide.columns]
    long = wide.melt(id_vars="date", value_vars=cols, var_name="location", value_name="wdpm")
    long = long[long["date"].dt.dayofweek.eq(6)]  # one row per week (Sundays, 7-day sums)
    long = long[(long["date"] >= cfg_m["desde"]) & (long["date"] <= cfg_m["hasta"])]
    v = vac[["location", "date", "people_fully_vaccinated"]].sort_values("date")
    v = (
        v.set_index("date").groupby("location")["people_fully_vaccinated"]
        .apply(lambda s: s.resample("D").last().ffill())
        .reset_index()
    )  # fmt: skip
    m = long.merge(v, on=["location", "date"], how="left")
    m["population"] = m["location"].map(pop)
    m = m.dropna(subset=["population"])
    m["people_fully_vaccinated"] = m["people_fully_vaccinated"].fillna(0)
    m.loc[m["date"] < "2020-12-01", "people_fully_vaccinated"] = 0
    out = pd.DataFrame(
        {
            "country": m["location"].map(SUDAMERICA),
            "week": m["date"],
            "population": m["population"].round(),
            "fully_vaccinated": m.groupby("location")["people_fully_vaccinated"].cummax(),
            "deaths": (m["wdpm"].fillna(0) * m["population"] / 1e6).round(),
        }
    ).reset_index(drop=True)
    out = _check_rows(out, "mortalidad")
    return out, {
        "rows": len(out),
        "filter": f"10 países de Sudamérica, semanas de {cfg_m['desde'][:7]} a {cfg_m['hasta'][:7]}",
    }


def salud_sintetica(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    weeks = pd.date_range("2020-03-01", "2022-12-25", freq="W-SUN")
    rows = []
    for c in SUDAMERICA.values():
        pop = rng.uniform(3e6, 2e8)
        start = pd.Timestamp("2021-02-14") + pd.Timedelta(days=int(rng.integers(0, 60)))
        for w in weeks:
            t = (w - weeks[0]).days / 7
            wave = 25 * np.exp(-(((t - 30) / 8) ** 2)) + 15 * np.exp(-(((t - 60) / 10) ** 2)) + 3
            cov = float(np.clip((w - start).days / 300, 0, 0.8)) if w > start else 0.0
            rows.append({"country": c, "week": w, "population": round(pop), "fully_vaccinated": round(pop * cov),
                         "deaths": round(max(wave * (1 - 0.7 * cov) * rng.normal(1, 0.1), 0) * pop / 1e6)})  # fmt: skip
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ telecom
def moviles_real() -> tuple[pd.DataFrame, dict]:
    cfg = fuentes()["moviles"]
    raw = pd.read_csv(fetch(cfg["descarga"], "tidytuesday-mobile.csv"))
    d = (
        raw[raw["entity"].isin(SUDAMERICA) & (raw["year"] >= cfg["desde"])]
        .sort_values(["entity", "year"])
        .copy()
    )

    # The source has no population after 2013: it is extended with each country's growth of the previous five years.
    def extend(s: pd.Series) -> pd.Series:
        s = s.copy()
        for i in range(len(s)):
            if pd.isna(s.iloc[i]) and i >= 5 and s.iloc[i - 5 : i].notna().all():
                g = (s.iloc[i - 1] / s.iloc[i - 5]) ** (1 / 4)
                s.iloc[i] = s.iloc[i - 1] * g
        return s

    d["population"] = d.groupby("entity")["total_pop"].transform(extend)
    d = d.dropna(subset=["population", "mobile_subs"])
    out = pd.DataFrame(
        {"country": d["entity"].map(SUDAMERICA), "year": d["year"].astype(int), "population": d["population"].round(),
         "lines": (d["mobile_subs"] * d["population"] / 100).round(), "estimated_population": d["total_pop"].isna()}
    ).reset_index(drop=True)  # fmt: skip
    out = _check_rows(out, "moviles")
    return out, {
        "rows": len(out),
        "filter": f"10 países de Sudamérica, {cfg['desde']} a {out['year'].max()}",
    }


def moviles_sintetica(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 2)
    rows = []
    for c in SUDAMERICA.values():
        pop, mid, top = rng.uniform(3e6, 2e8), rng.uniform(2006, 2011), rng.uniform(95, 150)
        for y in range(1995, 2018):
            pen = top / (1 + np.exp(-(y - mid) / 1.6))
            rows.append(
                {
                    "country": c,
                    "year": y,
                    "population": round(pop),
                    "lines": round(pop * pen / 100),
                    "estimated_population": False,
                }
            )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ educación
NIVELES = {"Primary Education": "Primaria", "Lower Secondary Education": "Secundaria (primer ciclo)",
           "Upper Secondary Education": "Secundaria (segundo ciclo)"}  # fmt: skip


def docentes_real() -> tuple[pd.DataFrame, dict]:
    cfg = fuentes()["docentes"]
    raw = pd.read_csv(fetch(cfg["descarga"], "tidytuesday-student-teacher-ratio.csv"))
    d = raw[raw["country"].isin(SUDAMERICA) & raw["indicator"].isin(NIVELES)].dropna(
        subset=["student_ratio"]
    )
    out = pd.DataFrame(
        {"country": d["country"].map(SUDAMERICA), "level": d["indicator"].map(NIVELES), "year": d["year"].astype(int),
         "student_ratio": d["student_ratio"].astype(float)}
    ).reset_index(drop=True)  # fmt: skip
    out = _check_rows(out, "docentes")
    return out, {
        "rows": len(out),
        "filter": f"10 países de Sudamérica, 3 niveles, {out['year'].min()} a {out['year'].max()}",
    }


def docentes_sintetica(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 3)
    rows = []
    for c in SUDAMERICA.values():
        base = rng.uniform(14, 28)
        for lvl, f in zip(NIVELES.values(), (1.0, 0.85, 0.8), strict=True):
            for y in range(2012, 2018):
                rows.append(
                    {
                        "country": c,
                        "level": lvl,
                        "year": y,
                        "student_ratio": round(base * f * rng.normal(1, 0.03), 2),
                    }
                )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ logística
FRANJAS = [(0, 6, "Madrugada (0 a 6 h)"), (6, 10, "Mañana (6 a 10 h)"), (10, 14, "Mediodía (10 a 14 h)"),
           (14, 18, "Tarde (14 a 18 h)"), (18, 24, "Noche (18 a 24 h)")]  # fmt: skip
DISTANCIAS = [
    (0, 500, "Corta (hasta 500 millas)"),
    (500, 1000, "Media (500 a 1 000 millas)"),
    (1000, 10_000, "Larga (más de 1 000 millas)"),
]


def _bands(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour_band"] = pd.cut(
        df["hour"], [b[0] for b in FRANJAS] + [24], labels=[b[2] for b in FRANJAS], right=False
    ).astype(str)
    df["distance_band"] = pd.cut(
        df["distance_miles"],
        [b[0] for b in DISTANCIAS] + [10_000],
        labels=[b[2] for b in DISTANCIAS],
        right=False,
    ).astype(str)
    df["hour_int"] = df["hour"].astype(int).clip(0, 23)
    return df


def vuelos_real() -> tuple[pd.DataFrame, dict]:
    cfg = fuentes()["vuelos"]
    raw = pd.DataFrame(
        json.loads(fetch(cfg["descarga"], "vega-flights-200k.json").read_text(encoding="utf-8"))
    )
    out = _bands(
        pd.DataFrame(
            {
                "delay_minutes": raw["delay"].astype(float),
                "distance_miles": raw["distance"].astype(float),
                "hour": raw["time"].astype(float),
            }
        )
    )
    out = _check_rows(out, "vuelos")
    return out, {
        "rows": len(out),
        "filter": "muestra de 200 000 vuelos publicada por vega-datasets (sin aerolínea ni fecha)",
    }


def vuelos_sintetica(seed: int = SEED, n: int = 40_000) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 4)
    hour = rng.uniform(5, 24, n)
    dist = rng.lognormal(np.log(600), 0.7, n).clip(30, 4900)
    late = rng.random(n) < (0.08 + 0.018 * (hour - 5))
    delay = np.where(late, rng.exponential(45, n) + 16, rng.normal(-3, 7, n))
    return _bands(
        pd.DataFrame({"delay_minutes": delay.round(), "distance_miles": dist.round(), "hour": hour})
    )


# ------------------------------------------------------------------ banca (siempre simulada)
ENTIDADES = {
    "Banca múltiple": (0.025, 0.55),
    "Financieras": (0.055, 0.12),
    "Cajas municipales": (0.045, 0.2),
    "Cajas rurales": (0.07, 0.05),
}
SEGMENTOS = {"Consumo": 0.3, "Pequeña empresa": 0.25, "Hipotecario": 0.25, "Corporativo": 0.2}
REGIONES = ["Lima", "Norte", "Sur", "Centro", "Oriente"]


def creditos_sintetica(seed: int = SEED) -> pd.DataFrame:
    """Monthly loan book by entity type, segment and region. The story: small-business loans deteriorate."""
    rng = np.random.default_rng(seed + 5)
    months = pd.date_range("2023-01-01", "2024-12-01", freq="MS")
    rows = []
    seg_risk = {"Consumo": 1.1, "Pequeña empresa": 1.6, "Hipotecario": 0.5, "Corporativo": 0.3}
    for ent, (base, size) in ENTIDADES.items():
        for seg, share in SEGMENTOS.items():
            if ent != "Banca múltiple" and seg == "Corporativo":
                continue
            for reg in REGIONES:
                bal0 = 1e9 * size * share * rng.uniform(0.5, 1.5)
                for i, m in enumerate(months):
                    trend = 1 + (0.025 * i if seg == "Pequeña empresa" and i >= 9 else 0)
                    npl = base * seg_risk[seg] * trend * rng.normal(1, 0.04)
                    bal = bal0 * (1.006**i)
                    rows.append({"month": m, "entity_type": ent, "segment": seg, "region": reg,
                                 "loan_balance": round(bal), "overdue_balance": round(bal * max(npl, 0))})  # fmt: skip
    return pd.DataFrame(rows)
