"""Load and validate the KPI catalog (kpis/catalog.yaml).

Validation happens in two layers:

1. Structural: the JSON Schema in kpis/catalog.schema.json.
2. Semantic: rules a schema cannot express (unique ids, related ids exist,
   thresholds consistent with the direction, every KPI has exactly one
   Python implementation, params referenced in DAX/SQL exist, ...).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import jsonschema
import yaml

from .paths import CATALOG_PATH, SCHEMA_PATH

PARAM_REF = re.compile(r"\$\{([a-z_]+)\}")


class CatalogError(ValueError):
    """Raised when the catalog breaks a structural or semantic rule."""


@dataclass(frozen=True)
class KPI:
    id: str
    name: str
    case: str
    question: str
    definition: str
    formula: str
    unit: str
    granularity: str
    direction: str
    target: float
    thresholds: dict[str, Any]
    owner: str
    source: str
    input: dict[str, Any]
    how_to_read: str
    misreadings: list[str]
    related: list[str]
    chart: dict[str, str]
    dax: str
    sql: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def render(self, template: str | None) -> str | None:
        """Substitute ${param} references in a DAX/SQL template."""
        if template is None:
            return None
        return Template(template).substitute(self.params)

    @property
    def dax_expression(self) -> str:
        return self.render(self.dax)  # type: ignore[return-value]

    @property
    def sql_query(self) -> str | None:
        return self.render(self.sql)


@dataclass(frozen=True)
class Catalog:
    version: int
    cases: dict[str, dict[str, Any]]
    kpis: dict[str, KPI]

    def __getitem__(self, kpi_id: str) -> KPI:
        try:
            return self.kpis[kpi_id]
        except KeyError as exc:
            raise KeyError(f"KPI '{kpi_id}' is not in the catalog") from exc

    def __iter__(self):
        return iter(self.kpis.values())

    def __len__(self) -> int:
        return len(self.kpis)

    def for_case(self, case: str) -> list[KPI]:
        return [k for k in self.kpis.values() if k.case == case]


def _semantic_errors(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ids = [k["id"] for k in raw["kpis"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        errors.append(f"duplicate KPI ids: {sorted(dupes)}")
    idset = set(ids)
    for k in raw["kpis"]:
        kid = k["id"]
        if k["case"] not in raw["cases"]:
            errors.append(f"{kid}: unknown case '{k['case']}'")
        table = k["input"]["table"]
        if table != "any" and table not in raw["cases"].get(k["case"], {}).get("tables", []):
            errors.append(f"{kid}: input table '{table}' is not declared for case '{k['case']}'")
        for rel in k["related"]:
            if rel not in idset:
                errors.append(f"{kid}: related KPI '{rel}' does not exist")
            if rel == kid:
                errors.append(f"{kid}: a KPI cannot be related to itself")
        green, amber = k["thresholds"]["green"], k["thresholds"]["amber"]
        direction, target = k["direction"], k["target"]
        if direction == "target_range":
            if not (isinstance(green, list) and isinstance(amber, list)):
                errors.append(f"{kid}: target_range thresholds must be [low, high] bands")
            else:
                if not (green[0] < green[1] and amber[0] < amber[1]):
                    errors.append(f"{kid}: bands must be [low, high] with low < high")
                if not (amber[0] <= green[0] and green[1] <= amber[1]):
                    errors.append(f"{kid}: amber band must contain the green band")
                if not (green[0] <= target <= green[1]):
                    errors.append(f"{kid}: target must lie inside the green band")
        else:
            if isinstance(green, list) or isinstance(amber, list):
                errors.append(f"{kid}: {direction} thresholds must be single numbers")
            elif direction == "higher_is_better" and not green >= amber:
                errors.append(f"{kid}: higher_is_better needs green >= amber")
            elif direction == "lower_is_better" and not green <= amber:
                errors.append(f"{kid}: lower_is_better needs green <= amber")
            elif direction == "higher_is_better" and target < green:
                errors.append(f"{kid}: target below the green threshold")
            elif direction == "lower_is_better" and target > green:
                errors.append(f"{kid}: target above the green threshold")
        if k["unit"] == "percent" and direction != "target_range":
            for name, value in (("target", target), ("green", green), ("amber", amber)):
                if not 0 <= value <= 1:
                    errors.append(f"{kid}: percent {name} must be a fraction in [0, 1]")
        params = k.get("params", {})
        for text_field in ("dax", "sql"):
            for ref in PARAM_REF.findall(k.get(text_field) or ""):
                if ref not in params:
                    errors.append(f"{kid}: {text_field} references unknown param '{ref}'")
    return errors


def validate(raw: dict[str, Any], *, check_registry: bool = True) -> None:
    """Raise CatalogError listing every problem found in a raw catalog dict."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    problems = [
        f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(raw), key=lambda e: list(e.absolute_path))
    ]
    if not problems:
        problems = _semantic_errors(raw)
    if not problems and check_registry:
        from .formulas import REGISTRY

        ids = {k["id"] for k in raw["kpis"]}
        missing = sorted(ids - REGISTRY.keys())
        orphan = sorted(REGISTRY.keys() - ids)
        if missing:
            problems.append(f"KPIs without a Python implementation: {missing}")
        if orphan:
            problems.append(f"Python formulas not declared in the catalog: {orphan}")
    if problems:
        raise CatalogError("Catalog is invalid:\n  - " + "\n  - ".join(problems))


def parse(raw: dict[str, Any]) -> Catalog:
    kpis = {k["id"]: KPI(**k) for k in raw["kpis"]}
    return Catalog(version=raw["version"], cases=raw["cases"], kpis=kpis)


def load_raw(path: Path = CATALOG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=4)
def load(path: Path = CATALOG_PATH) -> Catalog:
    """Load, validate and parse the catalog. Cached: the catalog is immutable at runtime."""
    raw = load_raw(path)
    validate(raw)
    return parse(raw)
