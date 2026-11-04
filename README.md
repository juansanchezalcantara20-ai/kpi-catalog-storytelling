# KPI catalog & storytelling

**The theory of a KPI does not depend on the tool.** Every KPI in this repository is
defined once (`kpis/catalog.yaml`), calculated once (`src/kpistory`) and presented in
two different tools: a static website (MkDocs + Plotly) and a Power BI semantic layer.

> Work in progress - catalog, engine, tests, data pipeline and cases 1-2 are complete.

```bash
pip install -e ".[dev]"
make test       # hand-calculated formula tests
make validate   # catalog schema + semantic checks
make all        # everything: lint, tests, data, pages, site (mkdocs build)
mkdocs serve    # browse the site locally
```
