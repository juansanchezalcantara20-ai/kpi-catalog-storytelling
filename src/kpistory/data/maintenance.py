"""Case 2 data: AI4I 2020 process data mapped to a machine fleet, plus a work-order generator.

Real source: UCI Machine Learning Repository, "AI4I 2020 Predictive Maintenance Dataset"
(Matzka, 2020), CC BY 4.0. 10,000 process records with machine-failure flags.

Plan B: AI4I is itself a synthetic dataset whose generation rules are published on its
UCI page. `generate_ai4i` re-implements those rules with a fixed seed, so the plan B
keeps the same columns, failure modes and physics-like relationships.

Mapping (an assumption of this portfolio, stated on the case page): the 10,000 records
are split into 10 contiguous blocks of 1,000 = 10 machines. Each record is one
4-hour production run; 4 runs per working day (two 8-hour shifts) over 2024.
"""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd

from .download import fetch

URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
SEED = 2020
N_MACHINES = 10
RUN_HOURS = 4.0
RUNS_PER_DAY = 4
FAILURE_MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]
FAILURE_LABEL = {
    "TWF": "Tool wear",
    "HDF": "Heat dissipation",
    "PWF": "Power",
    "OSF": "Overstrain",
    "RNF": "Random",
}
AI4I_COLUMNS = [
    "UDI", "Product ID", "Type", "Air temperature [K]", "Process temperature [K]",
    "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]", "Machine failure",
    "TWF", "HDF", "PWF", "OSF", "RNF",
]  # fmt: skip


# --------------------------------------------------------------------------- AI4I
def load_real() -> pd.DataFrame:
    path = fetch(URL, "ai4i2020.zip")
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        return parse_ai4i(io.BytesIO(zf.read(name)))


def parse_ai4i(buffer) -> pd.DataFrame:
    df = pd.read_csv(buffer)
    missing = [c for c in AI4I_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"AI4I file does not have the expected columns: {missing}")
    return df[AI4I_COLUMNS]


def generate_ai4i(n: int = 10_000, seed: int = SEED) -> pd.DataFrame:
    """Re-implementation of the published AI4I 2020 generation rules."""
    rng = np.random.default_rng(seed)
    types = rng.choice(["L", "M", "H"], size=n, p=[0.5, 0.3, 0.2])
    air = 300 + np.cumsum(rng.normal(0, 0.05, n))
    air = 300 + (air - air.mean()) / air.std() * 2  # random walk normalised to sd 2 K around 300 K
    process = air + 10 + np.cumsum(rng.normal(0, 0.02, n))
    process = (
        air + 10 + (process - air - 10 - (process - air - 10).mean()) / (process - air - 10).std()
    )
    # Torque ~ N(40, 10) Nm; speed ~ 1538 rpm, strongly anti-correlated with torque (as in AI4I).
    z = rng.normal(0, 1, n)
    torque = (40 + 10 * z).clip(3.8)
    rpm = (1538 - 0.88 * 179 * z + rng.normal(0, 179 * 0.47, n)).clip(1168, 2886)
    wear_step = pd.Series(types).map({"L": 2, "M": 3, "H": 5}).to_numpy()
    tool_wear = np.zeros(n, dtype=int)
    twf = np.zeros(n, dtype=int)
    wear, life = 0, rng.uniform(200, 240)
    for i in range(n):
        wear += wear_step[i]
        tool_wear[i] = wear
        if wear >= life:
            if rng.random() < 0.37:  # the tool fails instead of being replaced in time
                twf[i] = 1
            wear, life = 0, rng.uniform(200, 240)
    diff = process - air
    hdf = ((diff < 8.6) & (rpm < 1380)).astype(int)
    pw = torque * rpm * 2 * np.pi / 60
    pwf = ((pw < 3500) | (pw > 9000)).astype(int)
    limit = pd.Series(types).map({"L": 11000, "M": 12000, "H": 13000}).to_numpy()
    osf = (tool_wear * torque > limit).astype(int)
    rnf = (rng.random(n) < 0.001).astype(int)
    failure = ((twf + hdf + pwf + osf + rnf) > 0).astype(int)
    return pd.DataFrame(
        {
            "UDI": np.arange(1, n + 1),
            "Product ID": [f"{t}{rng.integers(10000, 60000)}" for t in types],
            "Type": types,
            "Air temperature [K]": air.round(1),
            "Process temperature [K]": process.round(1),
            "Rotational speed [rpm]": rpm.round().astype(int),
            "Torque [Nm]": torque.round(1),
            "Tool wear [min]": tool_wear,
            "Machine failure": failure,
            "TWF": twf,
            "HDF": hdf,
            "PWF": pwf,
            "OSF": osf,
            "RNF": rnf,
        }
    )


def runs_from_process(ai4i: pd.DataFrame) -> pd.DataFrame:
    """Map AI4I records to machines and run timestamps (see module docstring)."""
    df = ai4i.sort_values("UDI", ignore_index=True).copy()
    per_machine = int(np.ceil(len(df) / N_MACHINES))
    df["asset_id"] = [f"M{(i // per_machine) + 1:02d}" for i in range(len(df))]
    df["run_index"] = df.groupby("asset_id").cumcount()
    workdays = pd.bdate_range("2024-01-02", periods=per_machine // RUNS_PER_DAY + 1)
    day = workdays[(df["run_index"] // RUNS_PER_DAY).to_numpy()]
    df["run_start"] = day + pd.to_timedelta(
        6 + (df["run_index"] % RUNS_PER_DAY) * RUN_HOURS, unit="h"
    )
    flags = df[FAILURE_MODES].to_numpy()
    first = np.where(flags.any(axis=1), flags.argmax(axis=1), -1)
    df["failure_mode"] = [FAILURE_MODES[i] if i >= 0 else None for i in first]
    df.loc[df["Machine failure"].eq(0), "failure_mode"] = None
    # AI4I has a few rows with Machine failure = 1 and no mode flag: keep them as "Unknown".
    df.loc[df["Machine failure"].eq(1) & df["failure_mode"].isna(), "failure_mode"] = "UNK"
    return df


# --------------------------------------------------------------------- work orders
REPAIR_MEDIAN_H = {"TWF": 1.5, "HDF": 3.0, "PWF": 2.5, "OSF": 2.0, "RNF": 4.0, "UNK": 3.0}
LATE_PM_CREW = {"M07", "M08"}  # night-shift crew: PMs often slip, paper work orders logged late


def generate_work_orders(runs: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Work orders as they land from the maintenance system (with data-quality issues)."""
    rng = np.random.default_rng(seed + 1)
    rows = []
    fails = runs[runs["failure_mode"].notna()]
    for r in fails.itertuples():
        repair = rng.lognormal(np.log(REPAIR_MEDIAN_H[r.failure_mode]), 0.5)
        if rng.random() < 0.09:  # waiting for spare parts: the long tail of MTTR
            repair += rng.uniform(16, 60)
        created = r.run_start + pd.Timedelta(hours=float(rng.uniform(0, RUN_HOURS)))
        rows.append(
            {
                "asset_id": r.asset_id,
                "wo_type": "corrective",
                "planned": False,
                "created_at": created,
                "due_date": pd.NaT,
                "completed_at": created + pd.Timedelta(hours=repair),
                "repair_hours": repair,
                "labor_hours": repair * rng.choice([1, 2], p=[0.6, 0.4])
                if repair < 12
                else rng.uniform(4, 10),
                "failure_mode": r.failure_mode,
            }
        )
    # Tool changes done before failure (AI4I tool-wear resets) are planned replacements.
    wear = runs["Tool wear [min]"].to_numpy()
    reset = (
        np.r_[False, wear[1:] < wear[:-1]]
        & runs["asset_id"].eq(runs["asset_id"].shift()).to_numpy()
    )
    for r in runs[reset & runs["failure_mode"].shift().isna().to_numpy()].itertuples():
        rows.append(
            {
                "asset_id": r.asset_id, "wo_type": "tool_change", "planned": True,
                "created_at": r.run_start - pd.Timedelta(hours=1), "due_date": pd.NaT,
                "completed_at": r.run_start - pd.Timedelta(minutes=15), "repair_hours": np.nan,
                "labor_hours": 0.75, "failure_mode": None,
            }
        )  # fmt: skip
    # Weekly preventive maintenance per machine (due every Monday).
    for asset in sorted(runs["asset_id"].unique()):
        late_crew = asset in LATE_PM_CREW
        for due in pd.date_range("2024-01-08", "2024-12-23", freq="W-MON"):
            if late_crew and rng.random() < 0.10:
                completed = pd.NaT  # skipped
            else:
                p_late = 0.38 if late_crew else 0.06
                delay = rng.uniform(4, 15) if rng.random() < p_late else rng.uniform(-2, 2.5)
                completed = due + pd.Timedelta(days=float(delay)) + pd.Timedelta(hours=10)
            rows.append(
                {
                    "asset_id": asset, "wo_type": "preventive", "planned": True,
                    "created_at": due - pd.Timedelta(days=14), "due_date": due,
                    "completed_at": completed, "repair_hours": np.nan,
                    "labor_hours": float(rng.uniform(3.5, 6.0)), "failure_mode": None,
                }
            )  # fmt: skip
    wo = pd.DataFrame(rows).sort_values("created_at", ignore_index=True)
    wo.insert(0, "wo_id", [f"WO{200000 + i}" for i in range(len(wo))])
    lag = rng.exponential(2.0, len(wo))
    paper = wo["asset_id"].isin(LATE_PM_CREW).to_numpy() & (rng.random(len(wo)) < 0.35)
    lag[paper] = rng.uniform(24, 96, paper.sum())
    wo["logged_at"] = wo["completed_at"].fillna(wo["due_date"]) + pd.to_timedelta(lag, unit="h")
    # Data-quality defects
    corrective = wo.index[wo["wo_type"].eq("corrective")]
    wo.loc[
        rng.choice(corrective, size=max(1, int(len(corrective) * 0.03)), replace=False),
        "failure_mode",
    ] = None
    wo.loc[
        rng.choice(wo.index, size=max(1, int(len(wo) * 0.004)), replace=False), "labor_hours"
    ] = 0.0
    dupes = wo.sample(frac=0.003, random_state=seed)
    return pd.concat([wo, dupes]).sort_values("created_at", ignore_index=True)


def clean_work_orders(landing: pd.DataFrame) -> pd.DataFrame:
    from .. import catalog
    from ..formulas.maintenance import pm_on_time

    df = landing.drop_duplicates(subset="wo_id").copy()
    df.loc[df["wo_type"].eq("corrective") & df["failure_mode"].isna(), "failure_mode"] = "UNK"
    df = df[df["labor_hours"] > 0]
    tolerance = catalog.load()["pm_compliance"].params["tolerance_days"]
    df["pm_on_time"] = pm_on_time(df, tolerance).where(df["wo_type"].eq("preventive"))
    df["month"] = df["created_at"].dt.to_period("M").dt.start_time
    df["failure_label"] = df["failure_mode"].map({**FAILURE_LABEL, "UNK": "Unknown"})
    return df.reset_index(drop=True)


def asset_periods(runs: pd.DataFrame, work_orders: pd.DataFrame) -> pd.DataFrame:
    """Asset x month: operating hours, failures and unplanned downtime."""
    r = runs.assign(month=runs["run_start"].dt.to_period("M").dt.start_time)
    ops = r.groupby(["asset_id", "month"]).agg(
        operating_hours=("run_index", lambda s: len(s) * RUN_HOURS),
        failures=("failure_mode", lambda s: int(s.notna().sum())),
    )
    corr = work_orders[work_orders["wo_type"].eq("corrective")]
    down = (
        corr.groupby(["asset_id", "month"])["repair_hours"].sum().rename("unplanned_downtime_hours")
    )
    out = ops.join(down, how="left").fillna({"unplanned_downtime_hours": 0.0}).reset_index()
    out["scheduled_hours"] = out["operating_hours"] + out["unplanned_downtime_hours"]
    return out
