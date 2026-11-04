"""Cases 3 and 4 data: UCI Online Retail II (transactions of a UK online gift retailer).

Real source: UCI Machine Learning Repository, "Online Retail II" (Chen, 2019), CC BY 4.0.
~1.07M invoice lines, Dec 2009 - Dec 2011, with the classic defects: missing customer
ids, cancellations (invoice prefix "C"), negative quantities, zero prices, non-product
codes (postage, manual adjustments) and exact duplicate rows.

Plan B: `generate` produces a smaller transaction log with the same columns and the
same kinds of defects, driven by explicit behavioural assumptions (heterogeneous
customer purchase rates and lifetimes, Zipf-like SKU popularity, a Q4 gift season,
seasonal and fading SKUs). Seed fixed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .download import fetch

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SEED = 2011
COLUMNS = [
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
]
NON_PRODUCT_CODES = {
    "POST",
    "DOT",
    "M",
    "C2",
    "BANK CHARGES",
    "PADS",
    "D",
    "CRUK",
    "ADJUST",
    "AMAZONFEE",
    "S",
    "B",
}
START, END = pd.Timestamp("2009-12-01"), pd.Timestamp("2011-12-09")


# --------------------------------------------------------------------------- real
def load_real() -> pd.DataFrame:
    import zipfile

    path = fetch(URL, "online_retail_ii.zip", timeout=300)
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith((".xlsx", ".csv")))
        with zf.open(name) as fh:
            if name.lower().endswith(".csv"):
                return parse_retail_frames([pd.read_csv(fh, encoding="latin-1")])
            sheets = pd.read_excel(fh, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
            return parse_retail_frames(list(sheets.values()))


def parse_retail_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(frames, ignore_index=True)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Online Retail II file does not have the expected columns: {missing}")
    df = df[COLUMNS].copy()
    df["Invoice"] = df["Invoice"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Customer ID"] = pd.to_numeric(df["Customer ID"], errors="coerce")
    return df


# ---------------------------------------------------------------------- synthetic
def generate(seed: int = SEED, n_customers: int = 4200, n_skus: int = 900) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range(START, END, freq="D")
    # --- SKUs: popularity (Zipf-like), price, lifecycle, seasonality
    pop = 1 / np.arange(1, n_skus + 1) ** 0.9
    rng.shuffle(pop)
    price = np.round(rng.lognormal(np.log(2.5), 0.7, n_skus), 2).clip(0.29, 40)
    seasonal = rng.random(n_skus) < 0.15  # Christmas items
    launch = rng.integers(-200, len(days) - 120, n_skus).clip(0)
    life = rng.integers(150, 1200, n_skus)  # some SKUs fade out before the end
    codes = [
        f"{rng.integers(10000, 99999)}{rng.choice(['', 'A', 'B'], p=[0.8, 0.1, 0.1])}"
        for _ in range(n_skus)
    ]
    descriptions = [f"{'XMAS ' if s else ''}GIFT ITEM {i:04d}" for i, s in enumerate(seasonal)]
    # --- customers: acquisition date, purchase rate, lifetime, country
    # 45% of customers already exist when the log starts; the rest arrive over time.
    acquired = np.where(
        rng.random(n_customers) < 0.45, 0, rng.integers(0, len(days) - 30, n_customers)
    )
    rate = rng.gamma(0.9, 1 / 45, n_customers)  # orders per day
    lifetime = rng.exponential(420, n_customers)
    countries = rng.choice(
        ["United Kingdom", "Germany", "France", "EIRE", "Netherlands", "Spain", "Belgium"],
        p=[0.89, 0.025, 0.025, 0.02, 0.015, 0.0125, 0.0125],
        size=n_customers,
    )
    season = 1 + 0.9 * np.exp(-(((days.dayofyear.to_numpy() - 320) / 28.0) ** 2))  # Q4 peak
    rows = []
    inv_no = 489434
    for c in range(n_customers):
        start = acquired[c]
        end = min(len(days) - 1, int(start + lifetime[c]))
        span = np.arange(start, end + 1)
        if not len(span):
            continue
        p_order = (rate[c] * season[span]).clip(0, 0.9)
        order_days = span[rng.random(len(span)) < p_order]
        if not len(order_days):
            order_days = np.array([start])
        for d in order_days:
            day = days[d]
            alive = (launch <= d) & (d < launch + life)
            weight = (
                pop
                * alive
                * np.where(seasonal, np.where(day.month in (9, 10, 11, 12), 4.0, 0.05), 1.0)
            )
            if weight.sum() == 0:
                continue
            n_lines = int(rng.integers(3, 25))
            skus = rng.choice(
                n_skus,
                size=min(n_lines, int((weight > 0).sum())),
                replace=False,
                p=weight / weight.sum(),
            )
            ts = day + pd.Timedelta(hours=float(rng.uniform(8, 18)))
            qty = rng.choice(
                [1, 2, 3, 4, 6, 12, 24], size=len(skus), p=[0.18, 0.15, 0.1, 0.12, 0.15, 0.22, 0.08]
            )
            for s, q in zip(skus, qty, strict=True):
                rows.append(
                    (
                        str(inv_no),
                        codes[s],
                        descriptions[s],
                        int(q),
                        ts,
                        float(price[s]),
                        float(12346 + c),
                        countries[c],
                    )
                )
            inv_no += 1
    df = pd.DataFrame(rows, columns=COLUMNS)
    return _inject_quality_issues(df, rng)


def _inject_quality_issues(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    # Guest checkouts: ~1 in 4 invoices has no customer id.
    invoices = df["Invoice"].unique()
    guests = set(rng.choice(invoices, size=int(len(invoices) * 0.24), replace=False))
    df.loc[df["Invoice"].isin(guests), "Customer ID"] = np.nan
    # Cancellations: copy ~2% of lines with negative quantity and a "C" invoice.
    canc = df.sample(frac=0.02, random_state=int(rng.integers(1 << 31))).copy()
    canc["Invoice"] = "C" + canc["Invoice"]
    canc["Quantity"] = -canc["Quantity"]
    canc["InvoiceDate"] = canc["InvoiceDate"] + pd.to_timedelta(
        rng.uniform(1, 72, len(canc)), unit="h"
    )
    # Postage and manual lines; zero-price lines; exact duplicates.
    post = df.drop_duplicates("Invoice").sample(frac=0.04, random_state=1).copy()
    post["StockCode"], post["Description"], post["Quantity"], post["Price"] = (
        "POST",
        "POSTAGE",
        1,
        18.0,
    )
    df.loc[df.sample(frac=0.003, random_state=2).index, "Price"] = 0.0
    dupes = df.sample(frac=0.008, random_state=3)
    return pd.concat([df, canc, post, dupes]).sort_values("InvoiceDate", ignore_index=True)


# ------------------------------------------------------------------------- clean
def clean(landing: pd.DataFrame) -> pd.DataFrame:
    """All valid product sales lines (identified or not). Revenue = quantity x price."""
    df = landing.drop_duplicates().copy()
    df = df[~df["Invoice"].str.startswith("C")]
    df = df[~df["StockCode"].str.upper().isin(NON_PRODUCT_CODES)]
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]
    out = pd.DataFrame(
        {
            "invoice_id": df["Invoice"],
            "sku": df["StockCode"].str.upper(),
            "description": df["Description"].fillna("").astype(str),
            "quantity": df["Quantity"].astype(int),
            "unit_price": df["Price"].astype(float),
            "invoice_date": df["InvoiceDate"],
            "customer_id": df["Customer ID"].astype("Int64").astype(str).replace("<NA>", None),
            "country": df["Country"],
        }
    )
    out["revenue"] = out["quantity"] * out["unit_price"]
    return out.reset_index(drop=True)
