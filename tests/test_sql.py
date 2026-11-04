"""Reference SQL in the catalog returns the same hand-calculated results (run on SQLite)."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest
from hand_examples import BY_ID

from kpistory.catalog import load

WITH_SQL = [k for k in load() if k.sql]


def _to_sqlite(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S").where(out[col].notna(), None)
        elif pd.api.types.is_bool_dtype(out[col]):
            out[col] = out[col].astype(int)
    return out


def test_most_kpis_have_reference_sql():
    assert len(WITH_SQL) >= 20


@pytest.mark.parametrize("kpi", WITH_SQL, ids=lambda k: k.id)
def test_sql_matches_hand_calculation(kpi):
    example = BY_ID[kpi.id]
    con = sqlite3.connect(":memory:")
    _to_sqlite(example.table).to_sql(kpi.input["table"], con, index=False)
    (value,) = con.execute(kpi.sql_query).fetchone()
    assert value == pytest.approx(example.expected, rel=1e-6), example.working
