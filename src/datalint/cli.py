"""Command-line entry point.

    datalint validate --schema schema.json --input data.csv [--out-dir out] [--json]

Exit codes: 0 = all rows passed, 1 = some rows or columns failed, 2 = bad usage or schema.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .report import format_text, summarize, write_reports
from .schema import Schema, SchemaError
from .validate import validate_rows


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return [], []
        rows = [{k: (v if v is not None else "") for k, v in row.items() if k is not None} for row in reader]
        return list(reader.fieldnames), rows


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="datalint", description="Validate CSV data against a JSON schema.")
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="validate a CSV file and write reports")
    v.add_argument("--schema", required=True, type=Path, help="schema JSON file")
    v.add_argument("--input", required=True, type=Path, help="CSV file to validate")
    v.add_argument("--out-dir", type=Path, default=None, help="where to write clean.csv, exceptions.csv, summary.json")
    v.add_argument("--json", action="store_true", help="print the summary as JSON instead of text")
    v.add_argument("--limit", type=int, default=10, help="max issues to print in text mode")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        schema = Schema.load(args.schema)
    except (SchemaError, OSError) as e:
        print(f"schema error: {e}", file=sys.stderr)
        return 2
    try:
        header, rows = read_csv(args.input)
    except OSError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2

    results, file_issues = validate_rows(schema, rows, header)
    summary = summarize(results, file_issues)
    if args.out_dir is not None:
        write_reports(args.out_dir, schema, results, file_issues, summary)

    if args.json:
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        print(format_text(summary, file_issues, results, args.limit))
    return 0 if summary.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
