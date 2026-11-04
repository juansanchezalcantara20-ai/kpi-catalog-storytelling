# KPI catalog & storytelling

[![CI](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/actions/workflows/ci.yml/badge.svg)](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/actions/workflows/ci.yml)
[![Site](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/actions/workflows/pages.yml/badge.svg)](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/)

**The theory of a KPI does not depend on the tool.** In this repository every KPI is
**defined once** (`kpis/catalog.yaml`), **calculated once** (a tested Python engine) and
**presented in two layers**: a story website that explains each KPI through a business case, and an
interactive KPI dashboard for monitoring - both generated from the same catalog and published in the cloud.

**→ Story site: <https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/>**
**→ Dashboard: <https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/dashboard/>**

| | |
|---|---|
| **28 KPIs** in 5 domains | each with a business question, definition, formula, unit, granularity, direction, target and traffic-light thresholds, owner, source, how to read it, common misreadings, related KPIs and a recommended chart |
| **5 cases told as stories** | context → question → KPI → finding → decision → how we keep measuring |
| **Every formula tested** | a hand-calculated example per KPI, checked against the Python engine **and** the reference SQL |
| **Anti-pattern gallery** | the same data shown misleadingly and honestly, side by side |
| **Interactive dashboard** | all 28 KPIs as cards with status, sparkline and target; filters by domain and status; trend against the target in a detail panel |

## Five-minute tour

**1 · Every case opens with the KPIs that answer its question** - value, status *with an icon and a word* (never colour alone), target and the comparison period. Each tile links to the KPI's catalog page.

![KPI tiles of the service case](docs/img/case-service-tiles.png)

**2 · Chart titles are conclusions, computed from the data.** One highlight colour carries the message; everything else is context grey; the target is drawn.

![SLA compliance by queue](docs/img/case-service-queue.png)

**3 · Decomposing a KPI into its drivers.** Availability ≈ MTBF / (MTBF + MTTR): two machines fail too often, two others repair too slowly - two different decisions.

![MTBF vs MTTR by machine](docs/img/case-maintenance-scatter.png)

**4 · Direction matters.** Forecast bias is graded against a band, not "higher is better": the moving average under-forecasts the gift season (stockouts) and over-forecasts January (excess stock).

![Forecast bias by month](docs/img/case-inventory-bias.png)

**5 · Data quality measured like any other KPI**, coloured by status against its target - and "not measurable" where a source has no load timestamp, instead of a made-up 100%.

![Data-quality grid](docs/img/case-dq-grid.png)

**6 · The anti-pattern gallery** shows why the honest version is honest.

![Truncated axis vs honest axis](docs/img/antipattern-axis.png)

**7 · The dashboard** is the monitoring view of the same numbers: scan for ✕, click, read the trend against the target and how to read it.

![KPI dashboard](docs/img/dashboard.png)

## The cases

| # | Case | KPIs | Data |
|---|------|------|------|
| 1 | [Service operations & SLA](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/cases/service/) | first response, resolution time, SLA compliance, aged backlog, FCR, reopen rate | synthetic queue simulation |
| 2 | [Maintenance](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/cases/maintenance/) | MTBF, MTTR, availability, PM compliance, planned share | UCI AI4I 2020 + work-order generator |
| 3 | [Inventory & demand](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/cases/inventory/) | fill rate, OTIF, turnover, days of cover, stockouts, obsolescence, MAPE, WAPE, bias | UCI Online Retail II + stock simulation |
| 4 | [Customers](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/cases/customers/) | retention, repeat purchase, RFM revenue at risk, NPS | UCI Online Retail II + simulated survey |
| 5 | [Data quality as a KPI](https://juansanchezalcantara20-ai.github.io/kpi-catalog-storytelling/cases/data_quality/) | completeness, uniqueness, validity, timeliness | the landing data of cases 1-4 |

Every dataset has a **plan B**: a seeded synthetic generator with the same schema, documented in
[`cases/`](cases/README.md). The website's *Data sources* page shows which one each build used.

## How it fits together

```
kpis/catalog.yaml ──► kpistory.catalog  (JSON Schema + semantic validation)
        │                    │
        │                    ├─► kpistory.formulas   one @kpi function per KPI (Python)
        │                    └─► catalog `sql:`      reference SQL, tested on SQLite
        │
data (UCI or plan B) ─► kpistory.data ─► kpistory.engine ─┬─► kpistory.site      → story site (MkDocs + Plotly)
                                                          └─► kpistory.dashboard → interactive HTML dashboard
                                                                   both published on GitHub Pages
```

- **Single source of truth.** Validation fails if a catalog KPI has no Python function, a function has no
  catalog entry, a threshold contradicts the KPI's direction, a related KPI does not exist, or a SQL
  template references an undeclared parameter.
- **Parameters written once.** The 7-day backlog limit, the 3-day PM tolerance or the 180-day obsolescence
  limit live in `params:` and are substituted into Python and SQL.
- **Formulas are proven.** [`tests/hand_examples.py`](tests/hand_examples.py) holds one small table per KPI with
  the arithmetic written out and the expected value; the same examples run against the Python engine and the
  SQL, and appear on each KPI page of the site as a worked example.

## Run it - in the cloud

Nothing has to run on a local machine:

- **GitHub Actions** runs everything on every push: `CI` (lint, tests, catalog validation, a full offline build)
  and, on `main`, `Publish site` (real UCI downloads with plan-B fallback, story site, dashboard, GitHub Pages).
- **GitHub Codespaces** is the development environment: *Code → Codespaces → Create codespace* opens a
  container defined in [`.devcontainer/`](.devcontainer/devcontainer.json) that installs the package, runs
  `make all` and forwards the site preview on port 8000.

Inside the Codespace (or any machine):

```bash
pip install -e ".[dev]"
```

```bash
make all          # lint → tests → catalog validation → data → story pages → dashboard → mkdocs build --strict
```

```bash
mkdocs serve      # browse the site at http://127.0.0.1:8000
```

`make all SOURCE=synthetic` runs fully offline; the default `SOURCE=auto` tries the UCI downloads first.
Individual steps: `make test`, `make validate`, `make data`, `make site`, `make dashboard`.

## What this demonstrates

| What the job descriptions ask for | Where it is in this repository |
|---|---|
| **KPI and indicator design** (control de gestión, planning & control) | [`kpis/catalog.yaml`](kpis/catalog.yaml): question, definition, formula, granularity, direction, target and thresholds, owner, misreadings, related KPIs - for 28 KPIs across service, maintenance, inventory, customers and data quality |
| **Reading KPIs critically** | leading vs lagging pairs, mean vs median, fill rate vs OTIF, MAPE vs WAPE, bias with a band, NPS with margin of error, ratio of sums vs average of ratios - all in the catalog and the cases |
| **BI dashboards** | an interactive KPI dashboard generated from the catalog: cards with status and target, filters, sparklines, trend vs target, definitions on click |
| **SQL** | reference SQL for 23 KPIs (window functions for medians, conditional aggregation, sub-queries), tested against hand-calculated results |
| **Data storytelling** | five cases with the same narrative structure; titles that state conclusions; annotations on the finding; decisions sized with the data |
| **Dashboard design** | KPI tiles with status icons, a consistent colour-blind-safe palette, one message per chart, targets always visible, and an anti-pattern gallery |
| **Operational excellence & continuous improvement** | capacity gap and aged backlog (service), condition-based maintenance and spare parts (maintenance), seasonal forecasting and safety stock (inventory), win-back lists (customers) |
| **Data quality & governance** | completeness, uniqueness, validity and timeliness as KPIs with owners and a per-dataset rule file that works as a data contract |
| **Engineering hygiene** | Python package, `pytest` (100+ tests), `ruff`, GitHub Actions on every push, one command (`make all`) that rebuilds everything, a [decision log](docs/DECISIONS.md) |

## How this was built

I designed and directed this project; the code and text were written by **Claude Code** (Anthropic's coding
agent) following my brief: what to measure, the case list, the narrative structure, the chart rules, the
honesty constraints and the phases. Every design decision and its reason is recorded in
[`docs/DECISIONS.md`](docs/DECISIONS.md) - including the places where a first draft was wrong (a ticket
generator that produced no backlog, a chart title the data contradicted) and how it was corrected.

## Scope & limitations

- **Data.** Only public (UCI, CC BY 4.0) or synthetic data. No data, names, figures or cases from any employer
  or client. In the build session the UCI downloads were blocked by the sandbox's network policy, so the
  screenshots above use the plan-B generators; the published site is rebuilt by GitHub Actions and may use the
  real files - its *Data sources* page says which.
- **Findings illustrate the method.** With synthetic data (tickets, work orders, stock, survey - and everything
  in plan B) a finding is a consequence of the generator's documented assumptions, not evidence about a real
  operation. The pages say so where it matters (e.g. the NPS-by-segment link is an assumption).
- **Targets are illustrative**, chosen to make the traffic lights meaningful on this data.
- **Simplifications.** Stock, forecasting and delivery are simple, transparent policies (8-week moving average,
  weekly order-up-to) rather than a planning system; AI4I records are mapped to a 10-machine fleet by assumption.
- **Not in scope:** cost or margin per work order (left out on purpose).

## Repository map

```
kpis/                catalog.yaml (source of truth), catalog.schema.json, dq_rules.yaml
src/kpistory/        catalog, engine, formulas/, data/, viz/, site/, dashboard.py
tests/               hand_examples.py + tests for formulas, SQL, catalog, data
cases/               one README per case: data source, plan B generator, seed, assumptions
docs/                handwritten site pages, DECISIONS.md, screenshots (generated pages are not committed)
.devcontainer/       GitHub Codespaces environment (cloud development)
.github/workflows/   ci.yml (every push), pages.yml (publish story site + dashboard from main)
```

MIT licence. Author: Juan Luis Sánchez Alcántara.
