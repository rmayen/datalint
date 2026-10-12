"""Reconciliation summary and report writers."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .schema import Schema
from .validate import Issue, RowResult


@dataclass
class Summary:
    rows_read: int
    rows_passed: int
    rows_failed: int
    issues_total: int
    issues_by_code: dict[str, int]
    issues_by_field: dict[str, int]
    file_issues: int

    @property
    def ok(self) -> bool:
        return self.rows_failed == 0 and self.file_issues == 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def summarize(results: list[RowResult], file_issues: list[Issue]) -> Summary:
    all_issues = [i for r in results for i in r.issues]
    failed = sum(1 for r in results if not r.ok)
    return Summary(
        rows_read=len(results),
        rows_passed=len(results) - failed,
        rows_failed=failed,
        issues_total=len(all_issues),
        issues_by_code=dict(sorted(Counter(i.code for i in all_issues).items())),
        issues_by_field=dict(sorted(Counter(i.field for i in all_issues).items())),
        file_issues=len(file_issues),
    )


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def write_reports(out_dir: Path, schema: Schema, results: list[RowResult], file_issues: list[Issue], summary: Summary) -> dict[str, Path]:
    """Write clean.csv (normalized passing rows), exceptions.csv (failing rows + reasons), summary.json.

    The exceptions file keeps the original raw values so nothing is lost; the clean file holds
    normalized values (trimmed strings, canonical booleans, ISO dates).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "clean": out_dir / "clean.csv",
        "exceptions": out_dir / "exceptions.csv",
        "summary": out_dir / "summary.json",
    }
    with open(paths["clean"], "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(schema.names)
        for r in results:
            if r.ok:
                w.writerow(_cell(r.normalized[n]) for n in schema.names)

    with open(paths["exceptions"], "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "field", "code", "message", *schema.names])
        for i in file_issues:
            w.writerow([i.row, i.field, i.code, i.message, *[""] * len(schema.names)])
        for r in results:
            for i in r.issues:
                w.writerow([i.row, i.field, i.code, i.message, *[r.raw.get(n, "") for n in schema.names]])

    with open(paths["summary"], "w", encoding="utf-8") as fh:
        json.dump(summary.to_dict(), fh, indent=2)
    return paths


def format_text(summary: Summary, file_issues: list[Issue], results: list[RowResult], limit: int = 10) -> str:
    lines = [
        f"rows read:    {summary.rows_read}",
        f"rows passed:  {summary.rows_passed}",
        f"rows failed:  {summary.rows_failed}",
        f"issues:       {summary.issues_total}" + (f"  ({', '.join(f'{k}={v}' for k, v in summary.issues_by_code.items())})" if summary.issues_by_code else ""),
    ]
    shown = 0
    for i in file_issues:
        lines.append(f"  file: {i.message}")
    for r in results:
        for i in r.issues:
            if shown >= limit:
                break
            lines.append(f"  row {i.row}: {i.message}")
            shown += 1
    remaining = summary.issues_total - shown
    if remaining > 0:
        lines.append(f"  ... {remaining} more (see exceptions.csv)")
    lines.append("RESULT: PASS" if summary.ok else "RESULT: FAIL")
    return "\n".join(lines)
