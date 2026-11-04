"""Data sources page, generated from data/processed/manifest.json."""

from __future__ import annotations


def page(manifest: dict) -> str:
    md = [
        "# Data sources\n",
        "Generated at build time from `data/processed/manifest.json`. "
        f"Source mode of this build: **`{manifest['source_mode']}`** "
        "(`auto` = try the public download, fall back to the seeded synthetic generator).\n",
        "| Dataset | Origin in this build | Notes |",
        "|---|---|---|",
    ]
    for key in ("tickets", "process_data", "work_orders", "transactions", "inventory", "survey"):
        m = manifest[key]
        origin = "✓ real public data" if m["origin"] == "real" else "synthetic"
        name = f"[{m['name']}]({m['url']})" if m.get("url") else m["name"]
        publisher = f" - {m['publisher']}" if m.get("publisher") else ""
        md.append(f"| {name}{publisher} | {origin} | {m['note']} |")
    md.append(
        "\nEvery generator, its seed and its assumptions are documented in the "
        "[`cases/`](https://github.com/juansanchezalcantara20-ai/kpi-catalog-storytelling/tree/main/cases) "
        "folder of the repository. Public datasets are used under their CC BY 4.0 licences; no data, names "
        "or figures from any real employer or client are used anywhere in this project.\n"
    )
    md.append(f"\nBuilt: {manifest['generated_at']} (UTC).\n")
    return "\n".join(md)
