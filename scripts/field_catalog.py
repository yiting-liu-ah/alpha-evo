#!/usr/bin/env python3
"""Search bundled field metadata or sync a private BRAIN field catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brain_client import BrainClient
from research_core import FieldCatalog, atomic_write_json, utc_now


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_CATALOG = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"
PRIVATE_CATALOGS = SKILL_DIR / "private" / "catalogs"


def command_search(args: argparse.Namespace) -> int:
    catalog = FieldCatalog(Path(args.catalog))
    matches = catalog.search(
        args.keyword,
        category=args.category,
        field_type=args.type,
        limit=args.limit,
    )
    output = [
        {
            "id": value.get("id"),
            "description": value.get("description"),
            "type": value.get("type"),
            "category": value.get("category", {}).get("id"),
            "dataset": value.get("dataset", {}).get("id"),
            "coverage": value.get("coverage"),
            "alphaCount": value.get("alphaCount"),
            "userCount": value.get("userCount"),
        }
        for value in matches
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def command_sync(args: argparse.Namespace) -> int:
    client = BrainClient.from_environment(SKILL_DIR)
    try:
        client.authenticate()
        fields = client.list_data_fields(
            region=args.region,
            universe=args.universe,
            delay=args.delay,
            instrument_type=args.instrument_type,
        )
    finally:
        client.close()
    output = (
        Path(args.output)
        if args.output
        else PRIVATE_CATALOGS
        / f"wq_{args.region.lower()}_{args.universe.lower()}_delay{args.delay}_data_fields.json"
    )
    atomic_write_json(output, fields)
    metadata = {
        "generated_at": utc_now(),
        "query": {
            "instrumentType": args.instrument_type,
            "region": args.region,
            "universe": args.universe,
            "delay": args.delay,
        },
        "field_count": len(fields),
        "catalog": str(output),
    }
    atomic_write_json(output.with_name(output.stem + "_summary.json"), metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Typed BRAIN field catalog utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search")
    search.add_argument("keyword")
    search.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    search.add_argument("--category")
    search.add_argument("--type", choices=["MATRIX", "VECTOR", "GROUP", "SYMBOL", "UNIVERSE"])
    search.add_argument("--limit", type=int, default=20)
    search.set_defaults(func=command_search)

    sync = subparsers.add_parser("sync")
    sync.add_argument("--instrument-type", default="EQUITY")
    sync.add_argument("--region", required=True)
    sync.add_argument("--universe", required=True)
    sync.add_argument("--delay", type=int, required=True)
    sync.add_argument("--output")
    sync.set_defaults(func=command_sync)
    return parser


if __name__ == "__main__":
    try:
        arguments = build_parser().parse_args()
        sys.exit(arguments.func(arguments))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
