# Decision log

Every non-obvious choice in this repository, with the reason behind it. Newest
decisions are appended at the end of each phase.

## Phase 1 · Catalog, engine, tests, CI

| # | Decision | Why |
|---|----------|-----|
| 1 | **`kpis/catalog.yaml` is the single source of truth**, validated by a JSON Schema plus semantic checks in `kpistory.catalog`. | A schema catches typos and missing fields; semantic checks catch what a schema cannot (thresholds contradicting the direction, related KPIs that do not exist, params referenced in DAX that are not declared). |
| 2 | **One Python function per KPI**, registered with `@kpi("<id>")`. Validation fails if a catalog KPI has no function or a function has no catalog entry. | "Nothing is defined twice" has to be enforced by code, not by discipline. |
| 3 | Functions never contain targets, thresholds or parameters. Parameters (e.g. the 7-day backlog limit) live in `params:` and are substituted into DAX and SQL as `${name}`. | Changing a business rule is a one-line edit in the catalog that propagates to Python, SQL and Power BI. |
| 4 | DAX and SQL are stored next to the definition in the catalog rather than generated from a formula mini-language. | A DSL expressive enough for OTIF, retention and RFM would be harder to read than the DAX itself. Keeping the three implementations side by side makes review easy; tests verify Python and SQL agree on the hand examples. DAX cannot be executed here (see Phase 6). |
| 5 | **Ratios are stored as fractions**, displayed as percentages. | Avoids the classic "is 0.9 ninety percent or 0.9 percent?" bug between layers; Power BI format strings do the display. |
| 6 | Three directions: `higher_is_better`, `lower_is_better`, **`target_range`**. | Days of cover and forecast bias are bad in both directions; forcing them into "higher/lower is better" teaches the wrong reading. |
| 7 | Traffic-light boundaries are inclusive on the green side (SLA ≥ 90% is green). | Matches how targets are usually worded ("at least 90%") and is pinned by a test. |
| 8 | Empty denominators return NaN (shown as "n/a"), never 0. | Same semantics as DAX `DIVIDE`; a 0% SLA in a week with no tickets is a false alarm. |
| 9 | **MTTR is kept as a mean** (not a median). The median and the tail are shown next to it. | The identity Availability = MTBF / (MTBF + MTTR) only holds with means. The misreading is documented instead of redefining the KPI. |
| 10 | Resolution and first-response time **are medians** by definition. | They are customer-experience KPIs with heavy right tails; no identity depends on them, so the robust statistic wins. |
| 11 | Every KPI has a **hand-calculated example** (`tests/hand_examples.py`) with the expected value and the arithmetic written out. The same examples run against the reference SQL on SQLite. | Hand examples are the cheapest proof that a formula means what the definition says; running them through two implementations catches definition drift. |
| 12 | The chart-type enum in the schema **does not contain `pie`**. | The catalog recommends charts; it should not be able to recommend the chart the style rules ban. |
| 13 | RFM is a helper (segmentation), and the catalog KPI is **revenue at risk** (share of revenue in the "At risk" segment). | A segmentation is not a number with a target; the share of revenue at risk is, and it triggers a decision (win-back campaign). |
| 14 | NPS is computed as % promoters − % detractors on a −100…+100 scale, with a margin-of-error helper. | The two most common NPS errors are averaging the 0–10 scores and over-reading small samples; both are tested. |
| 15 | Data-quality KPIs are generic functions; the per-dataset rules live in `kpis/dq_rules.yaml`. | Lets the same four dimensions be measured on every dataset of the repo, which is the point of case 5. |
| 16 | Package layout `src/kpistory`, `pyproject.toml`, `ruff` for lint + format, `pytest`, a `Makefile` with `make all`. | Standard, boring and reproducible. `make all` is the single command that rebuilds everything. |
