"""Ingest -> clean -> derive every table used by the cases; write data/processed/*.parquet.

`source`:
  auto       try the public download; on any failure use the seeded synthetic plan B
  real       public download only (fail loudly if unavailable)
  synthetic  plan B only (fully offline and deterministic; used by CI tests)

The provenance of every dataset is written to data/processed/manifest.json and shown
on the site, so a reader always knows whether a chart comes from real or synthetic data.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd

from ..paths import PROCESSED_DIR
from . import customers, inventory, maintenance, quality, retail, tickets

SOURCES = {
    "process_data": {
        "name": "AI4I 2020 Predictive Maintenance Dataset",
        "publisher": "UCI Machine Learning Repository (Matzka, 2020), CC BY 4.0",
        "url": maintenance.URL,
    },
    "transactions": {
        "name": "Online Retail II",
        "publisher": "UCI Machine Learning Repository (Chen, 2019), CC BY 4.0",
        "url": retail.URL,
    },
}


def _acquire(
    name: str, real: Callable[[], pd.DataFrame], synthetic: Callable[[], pd.DataFrame], source: str
):
    info = dict(SOURCES[name])
    if source in ("auto", "real"):
        try:
            t0 = time.time()
            df = real()
            info.update(origin="real", note=f"downloaded and parsed in {time.time() - t0:.0f}s")
            return df, info
        except Exception as exc:
            if source == "real":
                raise
            info.update(
                origin="synthetic", note=f"plan B - download/parse failed: {str(exc)[:160]}"
            )
    else:
        info.update(origin="synthetic", note="plan B - synthetic requested explicitly")
    return synthetic(), info


def build(source: str = "auto") -> tuple[dict[str, pd.DataFrame], dict]:
    manifest: dict = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_mode": source,
    }
    landing: dict[str, pd.DataFrame] = {}
    tables: dict[str, pd.DataFrame] = {}

    # Case 1 - service (always synthetic: no suitable public ticket log)
    landing["tickets"] = tickets.generate()
    tables["tickets"] = tickets.clean(landing["tickets"])
    manifest["tickets"] = {
        "name": "Service desk tickets",
        "origin": "synthetic",
        "note": f"queue simulation, seed {tickets.SEED} (no suitable public dataset)",
    }

    # Case 2 - maintenance
    ai4i, manifest["process_data"] = _acquire(
        "process_data", maintenance.load_real, maintenance.generate_ai4i, source
    )
    landing["process_data"] = ai4i
    runs = maintenance.runs_from_process(ai4i)
    landing["work_orders"] = maintenance.generate_work_orders(runs)
    tables["runs"] = runs
    tables["work_orders"] = maintenance.clean_work_orders(landing["work_orders"])
    tables["asset_periods"] = maintenance.asset_periods(runs, tables["work_orders"])
    manifest["work_orders"] = {
        "name": "Maintenance work orders",
        "origin": "synthetic",
        "note": f"generated from the failures in the process data, seed {maintenance.SEED}",
    }

    # Cases 3 and 4 - retail demand and customers
    trx, manifest["transactions"] = _acquire(
        "transactions", retail.load_real, retail.generate, source
    )
    landing["transactions"] = trx
    tables["sales"] = retail.clean(trx)
    tables.update(inventory.simulate(tables["sales"]))
    manifest["inventory"] = {
        "name": "Stock, replenishment and delivery simulation",
        "origin": "synthetic",
        "note": f"policy simulation on the demand above, seed {inventory.SEED}",
    }
    tables["customer_sales"] = customers.identified_sales(tables["sales"])
    tables["customer_rfm"] = customers.build_rfm(tables["sales"])
    landing["survey"] = customers.generate_survey(tables["customer_rfm"])
    tables["survey"] = customers.clean_survey(landing["survey"])
    manifest["survey"] = {
        "name": "NPS survey (simulated)",
        "origin": "synthetic",
        "note": f"scores drawn per RFM segment, seed {customers.SEED}",
    }

    # Case 5 - data quality on the landing data
    tables.update(quality.measure(landing))
    return {**tables, **{f"landing_{k}": v for k, v in landing.items()}}, manifest


def _text_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Object columns that mix types (e.g. numbers typed into a text field) become strings for Parquet."""
    out = df.copy()
    for col in out.columns[out.dtypes.eq(object)]:
        kinds = out[col].dropna().map(type).unique()
        if len(kinds) > 1:
            out[col] = out[col].map(lambda v: None if pd.isna(v) else str(v)).astype("string")
    return out


def run(source: str = "auto") -> dict:
    t0 = time.time()
    try:
        tables, manifest = build(source)
        tables = {name: _text_safe(df) for name, df in tables.items()}
    except Exception as exc:
        if source != "auto":
            raise
        # Real data downloaded but broke a later step: publish plan B rather than nothing, and say why.
        print(
            f"  real-data build failed ({type(exc).__name__}: {str(exc)[:200]}); rebuilding with plan B"
        )
        tables, manifest = build("synthetic")
        manifest["source_mode"] = "auto (fell back to synthetic after a real-data error)"
        for key in ("process_data", "transactions"):
            manifest[key]["note"] = (
                f"plan B - real data failed downstream: {type(exc).__name__}: {str(exc)[:160]}"
            )
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    manifest["tables"] = {name: len(df) for name, df in tables.items()}
    (PROCESSED_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for key in ("tickets", "process_data", "work_orders", "transactions", "inventory", "survey"):
        print(f"  {key:<14} {manifest[key]['origin']:<9} {manifest[key]['note']}")
    print(f"Data ready in {time.time() - t0:.0f}s -> {PROCESSED_DIR}")
    return manifest


def load_tables() -> tuple[dict[str, pd.DataFrame], dict]:
    """Read every processed table (run `kpistory data` first)."""
    manifest_path = PROCESSED_DIR / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("No processed data. Run `python -m kpistory data` first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tables = {
        name: pd.read_parquet(PROCESSED_DIR / f"{name}.parquet") for name in manifest["tables"]
    }
    return tables, manifest
