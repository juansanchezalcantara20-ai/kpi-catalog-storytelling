"""Command line entry point: `kpistory <command>` (or `python -m kpistory`)."""

from __future__ import annotations

import argparse
import sys


def cmd_validate(_: argparse.Namespace) -> int:
    from .catalog import CatalogError, load

    try:
        catalog = load()
    except CatalogError as exc:
        print(exc, file=sys.stderr)
        return 1
    by_case = {c: len(catalog.for_case(c)) for c in catalog.cases}
    print(f"Catalog OK: {len(catalog)} KPIs -> {by_case}")
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    from .data.pipeline import run

    run(source=args.source)
    return 0


def cmd_site(_: argparse.Namespace) -> int:
    from .site.build import build

    build()
    return 0


def cmd_powerbi(_: argparse.Namespace) -> int:
    try:
        from .powerbi.export import export
    except ModuleNotFoundError:
        print("Power BI layer not available in this version.")
        return 0

    export()
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    for step in (cmd_validate, cmd_data, cmd_site, cmd_powerbi):
        code = step(args)
        if code:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kpistory", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate kpis/catalog.yaml").set_defaults(func=cmd_validate)
    for name, func, text in (
        ("data", cmd_data, "download (or synthesise) and clean every dataset"),
        ("all", cmd_all, "validate + data + site pages + Power BI layer"),
    ):
        p = sub.add_parser(name, help=text)
        p.add_argument(
            "--source",
            choices=["auto", "real", "synthetic"],
            default="auto",
            help="auto: try the public download, fall back to the seeded synthetic generator",
        )
        p.set_defaults(func=func)
    sub.add_parser("site", help="generate the MkDocs pages and charts").set_defaults(func=cmd_site)
    sub.add_parser("powerbi", help="generate the Power BI layer from the catalog").set_defaults(
        func=cmd_powerbi
    )
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
