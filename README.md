# KPI catalog & storytelling

**The theory of a KPI does not depend on the tool.** Every KPI in this repository is
defined once (`kpis/catalog.yaml`), calculated once (`src/kpistory`) and presented in
two different tools: a static website (MkDocs + Plotly) and a Power BI semantic layer.

> Work in progress - phase 1 (catalog, engine, formula tests, CI) is complete.

```bash
pip install -e ".[dev]"
make test       # hand-calculated formula tests
make validate   # catalog schema + semantic checks
```
