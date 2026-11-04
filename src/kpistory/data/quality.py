"""Case 5: measure the four data-quality KPIs on every landing dataset."""

from __future__ import annotations

import pandas as pd
import yaml

from ..engine import Engine
from ..formulas.data_quality import (
    completeness_counts,
    timeliness_counts,
    uniqueness_counts,
    validity_mask,
)
from ..paths import DQ_RULES_PATH


def load_rules() -> dict:
    with open(DQ_RULES_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["datasets"]


def measure(
    landing: dict[str, pd.DataFrame], engine: Engine | None = None
) -> dict[str, pd.DataFrame]:
    """Return dq_results (dataset x dimension), dq_columns (per-column completeness) and dq_rules (per rule)."""
    engine = engine or Engine()
    rules = load_rules()
    results, columns, rule_rows = [], [], []
    for name, cfg in rules.items():
        df = landing[name]
        passed, total = completeness_counts(df, cfg["required"])
        results.append((name, "completeness", passed, total))
        for col in cfg["required"]:
            p, t = completeness_counts(df, [col])
            columns.append({"dataset": name, "column": col, "value": p / t if t else float("nan")})
        passed, total = uniqueness_counts(df, cfg["key"])
        results.append((name, "uniqueness", passed, total))
        mask = validity_mask(df, list(cfg["rules"].values()))
        results.append((name, "validity", int(mask.sum()), len(df)))
        for label, rule in cfg["rules"].items():
            ok = validity_mask(df, [rule])
            rule_rows.append(
                {"dataset": name, "rule": label, "failed_rows": int((~ok).sum()), "rows": len(df)}
            )
        t = cfg.get("timeliness")
        if t:
            passed, total = timeliness_counts(df.dropna(subset=[t["event_col"]]), **t)
            results.append((name, "timeliness", passed, total))
        else:
            results.append((name, "timeliness", 0, 0))
    dq = pd.DataFrame(results, columns=["dataset", "dimension", "passed", "total"])
    dq["value"] = dq["passed"] / dq["total"].where(dq["total"] > 0)
    kpi_of = {d: f"dq_{d}" for d in ["completeness", "uniqueness", "validity", "timeliness"]}
    dq["status"] = [
        engine.status(kpi_of[d], v) for d, v in zip(dq["dimension"], dq["value"], strict=True)
    ]
    dq["label"] = dq["dataset"].map({k: v["label"] for k, v in rules.items()})
    return {
        "dq_results": dq,
        "dq_columns": pd.DataFrame(columns),
        "dq_rules": pd.DataFrame(rule_rows),
    }
