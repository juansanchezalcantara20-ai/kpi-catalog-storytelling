"""Case 1 data: synthetic service-desk tickets (there is no good public ticket log).

Story baked into the generator (documented in cases/01_service/README.md):
a product rollout raises Field Support demand by ~60% from September 2024 while
staffing stays flat (capacity is ~30% above the normal load). Congestion lengthens resolution times, ages the backlog and
pushes agents to close faster, which shows up as more reopenings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 7
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")
SNAPSHOT = pd.Timestamp("2024-12-31 23:59")

QUEUES = {  # base tickets per weekday, median service hours
    "Billing": (9, 6.0),
    "Technical": (12, 10.0),
    "Field Support": (8, 14.0),
    "Accounts": (6, 5.0),
}
PRIORITIES = ["P1", "P2", "P3", "P4"]
PRIORITY_P = [0.05, 0.17, 0.48, 0.30]
SLA_HOURS = {"P1": 8.0, "P2": 24.0, "P3": 72.0, "P4": 120.0}
PRIORITY_SPEED = {"P1": 0.2, "P2": 0.7, "P3": 1.0, "P4": 1.3}
CHANNELS = ["email", "phone", "chat", "portal"]
CHANNEL_P = [0.40, 0.25, 0.20, 0.15]
FCR_P = {"email": 0.58, "phone": 0.74, "chat": 0.78, "portal": 0.62}
ROLLOUT = pd.Timestamp("2024-09-01")


def generate(seed: int = SEED) -> pd.DataFrame:
    """Return the ticket table as it lands from the source system (with its data-quality issues).

    Each queue is simulated as a priority queue with a fixed daily capacity: agents pick
    the highest-priority, oldest tickets first. When demand exceeds capacity the backlog
    grows, and low-priority tickets wait longest - which is how SLA breaches build up.
    """
    rng = np.random.default_rng(seed)
    days = pd.date_range(START, END, freq="D")
    rows: list[dict] = []
    for queue, (base, service_h) in QUEUES.items():
        pending: list[dict] = []
        for day in days:
            weekend = day.day_of_week >= 5
            surge = queue == "Field Support" and day >= ROLLOUT
            lam = base * (0.3 if weekend else 1.0) * (1.6 if surge else 1.0)
            for created in sorted(
                day + pd.to_timedelta(rng.uniform(7, 19, rng.poisson(lam)), unit="h")
            ):
                prio = str(rng.choice(PRIORITIES, p=PRIORITY_P))
                channel = str(rng.choice(CHANNELS, p=CHANNEL_P))
                frt = rng.lognormal(
                    np.log(0.8 * PRIORITY_SPEED[prio] * (1.8 if surge else 1.0) + 0.1), 0.8
                )
                pending.append(
                    {
                        "created_at": created,
                        "first_response_at": created + pd.Timedelta(hours=frt),
                        "priority": prio,
                        "queue": queue,
                        "channel": channel,
                        "surge": surge,
                    }
                )
            capacity = rng.poisson(base * 1.3 * (0.3 if weekend else 1.0))
            pending.sort(key=lambda t: (t["priority"], t["created_at"]))
            picked, pending = pending[:capacity], pending[capacity:]
            for t in picked:
                if t["created_at"] >= day:  # picked up the day it arrived
                    start = t["created_at"] + pd.Timedelta(hours=float(rng.exponential(0.7)))
                else:  # waited in the queue overnight or longer
                    start = day + pd.Timedelta(hours=float(rng.uniform(8, 18)))
                service = rng.lognormal(np.log(service_h * PRIORITY_SPEED[t["priority"]]), 0.6)
                rushed = t["surge"]  # agents under pressure close faster and reopen more
                fcr = rng.random() < FCR_P[t["channel"]] * (0.85 if rushed else 1.0)
                reopened = rng.random() < (0.10 if rushed else 0.04)
                resolved = start + pd.Timedelta(
                    hours=service + (rng.uniform(24, 96) if reopened else 0)
                )
                t.update(
                    resolved_at=max(resolved, t["first_response_at"] + pd.Timedelta(minutes=10)),
                    contacts=1 if fcr else int(rng.integers(2, 5)),
                    reopened=bool(reopened),
                )
                rows.append(t)
        for t in pending:  # still waiting at the snapshot
            t.update(resolved_at=pd.NaT, contacts=1, reopened=False)
            rows.append(t)
    df = pd.DataFrame(rows).drop(columns="surge").sort_values("created_at", ignore_index=True)
    df.insert(0, "ticket_id", [f"T{100000 + i}" for i in range(len(df))])
    df["sla_target_hours"] = df["priority"].map(SLA_HOURS)
    df.loc[df["first_response_at"] > SNAPSHOT, "first_response_at"] = pd.NaT
    is_open = df["resolved_at"].isna() | (df["resolved_at"] > SNAPSHOT)
    df.loc[is_open, ["resolved_at"]] = pd.NaT
    df.loc[is_open, "reopened"] = False
    df["status"] = np.where(is_open, "open", "resolved")
    # Load timestamp: near real time, except a nightly batch that sometimes fails.
    lag_h = rng.exponential(0.3, len(df))
    late = rng.random(len(df)) < 0.025
    lag_h[late] = rng.uniform(25, 72, late.sum())
    df["logged_at"] = df["created_at"] + pd.to_timedelta(lag_h, unit="h")
    return _inject_quality_issues(df, rng)


def _inject_quality_issues(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Typical ticketing-system defects, so that case 5 has something real to measure."""
    df = df.copy()
    n = len(df)
    df.loc[rng.random(n) < 0.012, "channel"] = None  # integration drops the channel
    bad_clock = rng.choice(
        df.index[df["status"].eq("resolved")], size=int(n * 0.002), replace=False
    )
    df.loc[bad_clock, "resolved_at"] = df.loc[bad_clock, "created_at"] - pd.Timedelta(hours=2)
    dupes = df.sample(frac=0.005, random_state=int(rng.integers(1 << 31)))  # sync retries
    return pd.concat([df, dupes]).sort_values("created_at", ignore_index=True)


def clean(landing: pd.DataFrame) -> pd.DataFrame:
    """Analysis-ready tickets: de-duplicated, impossible timestamps removed, derived columns added."""
    from ..formulas.service import derive_ticket_columns

    df = landing.drop_duplicates(subset="ticket_id").copy()
    bad = df["resolved_at"].notna() & (df["resolved_at"] < df["created_at"])
    df = df[~bad]
    df["channel"] = df["channel"].fillna("unknown")
    df = derive_ticket_columns(df, SNAPSHOT)
    df["created_week"] = df["created_at"].dt.to_period("W-SUN").dt.start_time
    df["created_month"] = df["created_at"].dt.to_period("M").dt.start_time
    df["resolved_month"] = df["resolved_at"].dt.to_period("M").dt.start_time
    return df.reset_index(drop=True)
