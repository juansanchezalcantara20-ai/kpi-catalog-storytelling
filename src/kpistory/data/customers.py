"""Case 4 data: identified sales, RFM table and a simulated NPS survey.

There is no public NPS dataset linked to Online Retail II, so the survey is always
synthetic (stated on the case page). Scores depend on the customer's RFM segment -
an assumption, not a finding - so that the page can show how NPS should be computed
and read (by segment, with sample size and margin of error).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..formulas.customers import rfm_table

SEED = 404
# Probability of (detractor 0-6, passive 7-8, promoter 9-10) by RFM segment.
SCORE_MIX = {
    "Champions": (0.08, 0.30, 0.62),
    "Loyal": (0.14, 0.38, 0.48),
    "New / promising": (0.18, 0.40, 0.42),
    "Needs attention": (0.30, 0.40, 0.30),
    "At risk": (0.46, 0.34, 0.20),
    "Hibernating": (0.40, 0.38, 0.22),
}
RESPONSE_RATE = 0.30


def identified_sales(sales: pd.DataFrame) -> pd.DataFrame:
    return sales[sales["customer_id"].notna()].reset_index(drop=True)


def build_rfm(sales: pd.DataFrame) -> pd.DataFrame:
    snapshot = sales["invoice_date"].max().normalize() + pd.Timedelta(days=1)
    return rfm_table(identified_sales(sales), snapshot=snapshot, window_days=365)


def generate_survey(rfm: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """One survey wave sent to every customer in the RFM window; ~30% respond."""
    rng = np.random.default_rng(seed)
    responders = rfm[rng.random(len(rfm)) < RESPONSE_RATE]
    rows = []
    end = pd.Timestamp("2011-12-09")
    for r in responders.itertuples():
        det, pas, pro = SCORE_MIX[r.segment]
        group = rng.choice(3, p=[det, pas, pro])
        score = (
            int(rng.choice([0, 1, 2, 3, 4, 5, 6], p=[0.04, 0.03, 0.06, 0.1, 0.15, 0.27, 0.35]))
            if group == 0
            else (
                int(rng.choice([7, 8])) if group == 1 else int(rng.choice([9, 10], p=[0.55, 0.45]))
            )
        )
        responded = end - pd.Timedelta(days=float(rng.uniform(0, 90)))
        rows.append(
            {
                "customer_id": r.customer_id,
                "score": score,
                "responded_at": responded,
                "segment": r.segment,
            }
        )
    df = pd.DataFrame(rows)
    df.insert(0, "response_id", [f"R{500000 + i}" for i in range(len(df))])
    df["loaded_at"] = df["responded_at"] + pd.to_timedelta(rng.exponential(6, len(df)), unit="h")
    # Defects: a survey tool export that sometimes types 11 on a 0-10 scale, and re-sent rows.
    df.loc[rng.choice(df.index, size=max(1, len(df) // 250), replace=False), "score"] = 11
    dupes = df.sample(frac=0.01, random_state=seed)
    return pd.concat([df, dupes]).sort_values("responded_at", ignore_index=True)


def clean_survey(landing: pd.DataFrame) -> pd.DataFrame:
    df = landing.drop_duplicates(subset="response_id")
    return df[df["score"].between(0, 10)].reset_index(drop=True)
