# KPI catalog & storytelling

**The theory of a KPI does not depend on the tool.** Each KPI here is *defined once*
in a YAML catalog, *calculated once* by a tested Python engine, and *presented in two tools*:
this website and a Power BI semantic layer generated from the same catalog.

<div class="grid cards" markdown>

- **[Five business cases](cases/service.md)** - service SLA, maintenance, inventory,
  customers and data quality, each told as *context → question → KPI → finding → decision → how we keep measuring*.
- **[Anti-pattern gallery](antipatterns.md)** - the same data shown wrong and right, side by side.
- **[KPI catalog](catalog/index.md)** - definition, formula, target, owner, how to read it,
  common misreadings, DAX, SQL and a hand-calculated worked example for every KPI.

</div>

## Why this exists

A dashboard is only as good as the definitions behind it. Most KPI problems are not tool
problems: an average that hides a long tail, a fill rate that looks fine while customers get
incomplete orders, a forecast error metric dominated by slow movers, a green traffic light
with no target behind it. This site shows how each KPI is defined, read and turned into a
decision, and the [method page](method.md) lists the chart rules every page follows.

!!! note "Data"
    Only public (UCI, CC BY 4.0) or synthetic data. With synthetic data the findings
    illustrate the method; they are not claims about a real organisation. See
    [data sources](data-sources.md).
