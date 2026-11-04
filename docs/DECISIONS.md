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

## Phase 2 · Ingestion, cleaning and plan B

| # | Decision | Why |
|---|----------|-----|
| 17 | Data source mode `auto` (default): try the public download, fall back to the seeded generator on **any** error; `real` and `synthetic` force one path. | Rule: a network failure must never stop the build. CI tests use `synthetic` for determinism; the site build uses `auto`. |
| 18 | Provenance is written to `data/processed/manifest.json` and printed on the site. | A reader must always know whether a chart is real or synthetic data. |
| 19 | **In the build session, both UCI downloads failed** (the sandbox proxy blocked `archive.ics.uci.edu`, HTTP 403), so the committed screenshots use plan B. GitHub Actions can reach UCI, so the published site may use the real files. | Honest reporting; the page texts are generated from the data, so they stay correct either way. |
| 20 | Service tickets are **always synthetic** and generated with a **priority-queue simulation with daily capacity**, not with independent random durations. | No public ticket log has SLA targets and reopenings. A first version with independent durations produced no backlog at all - unrealistic. Queues with capacity produce backlog, ageing and SLA breaches the way service desks really do. |
| 21 | AI4I plan B re-implements the **published generation rules** of AI4I. | AI4I is itself synthetic; reproducing its rules keeps the failure physics (tool wear × torque → overstrain) that the case relies on. |
| 22 | AI4I records are mapped to 10 machines × 1,000 contiguous 4-hour runs. | AI4I has no machine id or timestamp. Contiguous blocks keep the tool-wear sequence intact; the assumption is stated on the page. |
| 23 | Work orders, stock, forecast, deliveries and the NPS survey are simulated with **explicit, documented policies** (see `cases/*/README.md`). | The public data covers demand and process; the operational half is simulated transparently instead of being presented as observed. |
| 24 | The forecast is an **8-week moving average** on purpose. | It is the most common baseline in practice, and its lag around the Q4 season produces the bias / stockout / excess pattern the case explains. |
| 25 | Stockout rate counts the **active assortment** only (between a SKU's first and last demand). | The first simulation showed 18% stockouts, almost all of them SKUs not yet launched or already discontinued. The catalog definition, DAX, SQL and the hand example were updated together. |
| 26 | Data quality is measured on the **landing** tables (before cleaning); cleaning rules are code (`clean*` functions). | Measuring after cleaning would always show 100%; the gap between landing and clean data is the DQ story. |
| 27 | Processed tables are Parquet (`pyarrow`). | Keeps dtypes (timestamps, booleans) between pipeline and site without re-parsing. |

## Phase 3 · Site and cases 1-2

| # | Decision | Why |
|---|----------|-----|
| 28 | **MkDocs Material** instead of Quarto. | Pure Python (`pip install`), no extra toolchain in CI; Material gives navigation, admonitions and tables out of the box. |
| 29 | Pages are **generated Markdown** (`src/kpistory/site`) with Plotly charts inlined as HTML; generated pages are not committed. | Every number in a title or sentence comes from the data at build time, so the text cannot drift from the charts, and it stays correct if the build uses the real UCI files instead of plan B. |
| 30 | **plotly.js is served from the site itself** (copied from the Python package) and loaded in `<head>`. | No CDN dependency (the build sandbox could not reach CDNs either), and inline chart scripts need Plotly defined before they run. |
| 31 | Chart titles are **conclusions computed from the data**; the subtitle says what is plotted. Long titles are wrapped automatically. | The style rule "title = conclusion" only survives data changes if the conclusion is computed, not typed. |
| 32 | One highlight colour (blue `#2a78d6`) + context grey; orange/aqua only when a comparison needs a second/third series; status colours (`#0ca30c` / `#fab219` / `#d03b3b`) reserved for good/watch/act and always paired with ✓ / ! / ✕ and a word. | Colour-blind-safe order validated by the palette tool used to design it; status must never be colour alone. |
| 33 | Bars start at zero, **except** the availability-by-machine chart, which says so in its subtitle and in a note. | All machines sit between 75% and 100%; the decision is the gap to a 97% target. Breaking the rule openly is better than hiding it (the anti-pattern gallery shows the dishonest version). |
| 34 | SLA trend and similar line charts may zoom the y-axis, stating the start in the subtitle. | Lines encode change by slope, not length; zooming is legitimate if declared. |
| 35 | Each low-availability machine is classified as **"fails too often" vs "too slow to repair"** by comparing its MTBF and MTTR gaps to the fleet medians. | A first draft labelled all low-availability machines as reliability problems; the scatter showed two of them were repair-time problems. The text is now computed per machine. |
| 36 | Quadrant lines in the MTBF/MTTR scatter use **fleet medians, not targets**. | With an illustrative 150 h MTBF target every machine would sit in the same quadrant; medians answer "which machines are different?". |
| 37 | Every chart has a "Show the data" table where the data is small enough. | Accessibility (a table view) and auditability for a reviewer. |
| 38 | `make all` runs lint → tests → validate → data → pages → Power BI layer → `mkdocs build --strict`; the Pages workflow runs exactly that with `SOURCE=auto` and caches `data/raw`. | One command reproduces everything, locally and in CI. |

## Phase 4 · Cases 3, 4 and 5

| # | Decision | Why |
|---|----------|-----|
| 39 | Case KPIs use the **last 12 months** of the log; snapshot KPIs (cover, obsolescence, RFM) use the last date. | A year is the shortest window that contains one full gift season. |
| 40 | Forecast evaluation keeps **complete weeks and complete months only**. | The log ends on a Friday in December; the partial month first showed a fake +80% over-forecast. |
| 41 | The MAPE vs WAPE chart groups SKU-weeks **by the size of the actual week**, not by ABC class. | A first version grouped by ABC class and its title ("slow movers inflate MAPE") was contradicted by the bars: A-class SKUs had the highest MAPE because their small weeks are intermittent. The mechanism is the size of the week, so that is what the chart shows. |
| 42 | Titles that make a causal-sounding claim are **conditional on the data** (e.g. stockouts vs under-forecast months: the title and the decision change if fewer than half of stockout days fall in under-forecast months). | A computed number inside a hard-coded claim can still lie; the claim itself has to be computed. |
| 43 | OTIF failures are decomposed into **short / late / both**, with the owner of each. | Fill rate and OTIF disagree by design; the decomposition turns the gap into two action owners. |
| 44 | Retention uses **complete quarters only**; the last partial quarter is dropped. | A quarter with three weeks of data looks like a churn crisis. |
| 45 | The NPS composition is the site's **only part-to-whole chart: a 100% bar with exactly three parts**. NPS by segment is shown with 95% margins of error. | Within the "no pies with more than three parts" rule, and NPS without n and error bars invites over-reading. |
| 46 | The NPS-segment relationship is **declared an assumption** on the page. | Scores were generated per segment, so presenting the link as a finding would be circular. |
| 47 | The data-quality grid colours cells by **status against the catalog target**, never by raw value, and shows "not measurable" instead of a value where no load timestamp exists. | A 99.2% can be a problem (uniqueness) while 96% is fine elsewhere; and an invented 100% would hide a missing audit column. |

## Phase 5 · Anti-pattern gallery

| # | Decision | Why |
|---|----------|-----|
| 48 | Six pairs, each built from the **cases' own data**: truncated axis, mean vs median, too many series, pie vs bars, traffic light without target, dual axis. | The five requested plus the dual axis, the most common way to invent a correlation. Using the cases' data shows the honest version is the one actually used. |
| 49 | Misleading charts use **library-default habits** (descriptive titles, rainbow colours, legends) rather than exaggerated strawmen. | The gallery is credible only if the left side looks like something people really publish. |
| 50 | The traffic-light pair colours the misleading side **relative to the fleet average**. | It is the subtle and common version of "status without a target": half the fleet is red by construction. |
| 51 | The "too many series" message is chosen by the data (the top-10 SKU whose demand dropped most) with a conditional title. | A first draft claimed a SKU was "seasonal" with 29% of its year in Q4 - barely above the 25% of a flat year. The claim was replaced by one the data supports. |
| 52 | CI also runs `make all SOURCE=synthetic` on every push. | The site generator is code too; a broken page should fail the build, not the deploy. |

## Phase 6 · Power BI layer

| # | Decision | Why |
|---|----------|-----|
| 53 | **No PBIP/TMDL project.** The repository ships `powerbi/measures.dax`, `powerbi/MODEL.md` and `powerbi/BUILD_CHECKLIST.md` instead. | Power BI Desktop cannot run in the build environment, so a generated TMDL project could not be opened to prove it valid. Shipping an unverified project as if it worked would be dishonest; the fallback is what was asked for in that case. |
| 54 | `measures.dax` is written in **DAX query view format** (`DEFINE MEASURE … EVALUATE ROW(…)`). | Desktop's DAX query view can add every measure to the model in one step, and the `EVALUATE` returns all KPIs in one row for reconciliation. |
| 55 | `expected_values.csv` (Python results on the same data) is exported next to the model tables, with the filter context needed where the KPI is time-relative. | Turns "trust me, the DAX matches" into a five-minute check in Desktop. |
| 56 | Rule-dependent flags (`within_sla`, `pm_on_time`, `active`) are **computed in Python and exported as columns**. | The rule is written once with its catalog parameter; DAX only counts the flag. |
| 57 | Measure names are the catalog names stripped of brackets and symbols; each measure lives in its KPI's input table. | Avoids escaping problems in DAX object names and keeps measures next to the facts they count. |
| 58 | The committed Power BI files are **tested to be identical to what the catalog generates**; data CSVs are not committed. | Guarantees the DAX in the repository is the DAX in the catalog. CSVs are reproducible with `make data powerbi` (and on a normal network will contain the real UCI data). |
| 59 | `powerbi/theme.json` is generated from the same palette module as the website. | Two tools, one visual language. |

## Phase 7 · README and release

| # | Decision | Why |
|---|----------|-----|
| 60 | README screenshots are cropped elements of the real built site (Playwright, 2× scale), committed in `docs/img/`. | A recruiter skimming GitHub sees the work without opening the site; crops of real pages cannot drift into mock-ups. |
| 61 | The README maps each requirement of the target job descriptions to a concrete file or page ("What this demonstrates"). | Five-minute review: claims are verifiable by clicking. |
| 62 | "How this was built" and "Scope & limitations" are explicit about Claude Code, synthetic data, illustrative targets and the unexecuted Power BI layer. | Honesty is part of the method being demonstrated. |
| 63 | The repository and Pages URLs assume the name `kpi-catalog-storytelling` under `juansanchezalcantara20-ai`. | The build session had no repository attached; if the name differs, update `mkdocs.yml` (`repo_url`) and the README links. |

## Phase 8 · Cloud-only development

| # | Decision | Why |
|---|----------|-----|
| 64 | **All development and builds run in the cloud**: GitHub Actions for CI and publishing, GitHub Codespaces (`.devcontainer/`) for editing and previewing. | Requirement: no local setup. The devcontainer installs the package and runs `make all`, so a Codespace is ready to work in minutes. |
| 65 | The Pages workflow **publishes the Power BI model tables** (`/data/powerbi/*.csv` + `manifest.json`) and uploads a `powerbi-layer` artifact. | Power BI Desktop loads them with *Get data → Web*; no Python on the PC, and the tables come from the same cloud build (with the real UCI data when reachable) as the website. |
| 66 | Power BI Desktop remains the only local step. | It is a Windows desktop application; the cloud equivalents (Power BI Service) cannot create measures from a DAX script without a desktop-authored model. |
