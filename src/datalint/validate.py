"""Row validation. Pure functions: rows in, results out. No I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from .schema import Field, Schema

TRUE = {"true", "t", "yes", "y", "1"}
FALSE = {"false", "f", "no", "n", "0"}


@dataclass(frozen=True)
class Issue:
    row: int  # 1-based data row number (header is row 0)
    field: str
    code: str
    message: str


@dataclass
class RowResult:
    row: int
    raw: dict[str, str]
    normalized: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def coerce(f: Field, raw: str) -> tuple[Any, str | None]:
    """Convert a raw cell to the field's type. Returns (value, error_code)."""
    text = raw.strip()
    if f.type == "string":
        return text, None
    if f.type == "enum":
        return (text, None) if text in f.values else (text, "not_in_enum")
    if f.type == "int":
        try:
            return int(text), None
        except ValueError:
            return text, "not_int"
    if f.type == "float":
        try:
            return float(text.replace(",", "")), None
        except ValueError:
            return text, "not_float"
    if f.type == "bool":
        low = text.lower()
        if low in TRUE:
            return True, None
        if low in FALSE:
            return False, None
        return text, "not_bool"
    if f.type == "date":
        try:
            return datetime.strptime(text, f.format).date(), None
        except ValueError:
            return text, "bad_date"
    return text, "unknown_type"  # pragma: no cover - schema rejects unknown types


def check_field(f: Field, raw: str | None, row: int) -> tuple[Any, list[Issue]]:
    issues: list[Issue] = []
    if raw is None or raw.strip() == "":
        if f.required:
            issues.append(Issue(row, f.name, "missing", f"'{f.name}' is required"))
        return None, issues

    value, code = coerce(f, raw)
    if code:
        detail = f" (expected one of: {', '.join(f.values)})" if code == "not_in_enum" else ""
        if code == "bad_date":
            detail = f" (expected format {f.format})"
        issues.append(Issue(row, f.name, code, f"'{f.name}' value {raw!r} is not a valid {f.type}{detail}"))
        return value, issues

    if f.regex is not None and not f.regex.search(str(value)):
        issues.append(Issue(row, f.name, "pattern", f"'{f.name}' value {raw!r} does not match pattern {f.pattern}"))
    if f.type in ("int", "float"):
        if f.min is not None and value < f.min:
            issues.append(Issue(row, f.name, "below_min", f"'{f.name}' value {value} is below minimum {f.min}"))
        if f.max is not None and value > f.max:
            issues.append(Issue(row, f.name, "above_max", f"'{f.name}' value {value} is above maximum {f.max}"))
    return value, issues


def validate_rows(schema: Schema, rows: Iterable[dict[str, str]], header: list[str] | None = None) -> tuple[list[RowResult], list[Issue]]:
    """Validate every row. Returns (per-row results, file-level issues such as missing columns).

    Rows are never dropped: a failing row is returned with its issues so the caller can route it
    to an exceptions report instead of silently discarding it.
    """
    file_issues: list[Issue] = []
    if header is not None:
        missing = [n for n in schema.names if n not in header]
        extra = [h for h in header if h not in schema.names]
        for n in missing:
            file_issues.append(Issue(0, n, "missing_column", f"column '{n}' is declared in the schema but absent from the file"))
        if extra and not schema.allow_extra_columns:
            for h in extra:
                file_issues.append(Issue(0, h, "unexpected_column", f"column '{h}' is not declared in the schema"))

    results: list[RowResult] = []
    seen: dict[str, dict[Any, int]] = {f.name: {} for f in schema.fields if f.unique}

    for i, raw in enumerate(rows, start=1):
        r = RowResult(row=i, raw=raw)
        for f in schema.fields:
            value, issues = check_field(f, raw.get(f.name), i)
            r.normalized[f.name] = value
            r.issues.extend(issues)
            if f.unique and value is not None and not issues:
                first = seen[f.name].get(value)
                if first is not None:
                    r.issues.append(Issue(i, f.name, "duplicate", f"'{f.name}' value {value!r} already appeared on row {first}"))
                else:
                    seen[f.name][value] = i
        results.append(r)
    return results, file_issues
