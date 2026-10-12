"""Schema definition: what a valid row looks like.

A schema is a JSON document such as:

    {
      "primary_key": "id",
      "fields": [
        {"name": "id", "type": "int", "required": true, "unique": true},
        {"name": "email", "type": "string", "required": true, "pattern": "^[^@]+@[^@]+$"},
        {"name": "amount", "type": "float", "min": 0},
        {"name": "status", "type": "enum", "values": ["active", "closed"]},
        {"name": "signed_on", "type": "date", "format": "%Y-%m-%d"}
      ]
    }
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TYPES = ("string", "int", "float", "bool", "date", "enum")


class SchemaError(ValueError):
    """Raised when the schema document itself is malformed."""


@dataclass(frozen=True)
class Field:
    name: str
    type: str = "string"
    required: bool = False
    unique: bool = False
    min: float | None = None
    max: float | None = None
    pattern: str | None = None
    values: tuple[str, ...] = ()
    format: str = "%Y-%m-%d"
    regex: re.Pattern[str] | None = field(default=None, compare=False, repr=False)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Field":
        if not isinstance(d, dict) or "name" not in d or not str(d["name"]).strip():
            raise SchemaError("every field needs a non-empty 'name'")
        name = str(d["name"])
        ftype = d.get("type", "string")
        if ftype not in TYPES:
            raise SchemaError(f"field '{name}': unknown type '{ftype}' (expected one of {', '.join(TYPES)})")
        if ftype == "enum" and not d.get("values"):
            raise SchemaError(f"field '{name}': enum fields need a non-empty 'values' list")
        for bound in ("min", "max"):
            if bound in d and ftype not in ("int", "float"):
                raise SchemaError(f"field '{name}': '{bound}' only applies to int or float fields")
        pattern = d.get("pattern")
        regex = None
        if pattern is not None:
            try:
                regex = re.compile(pattern)
            except re.error as e:
                raise SchemaError(f"field '{name}': invalid pattern: {e}") from e
        return Field(
            name=name,
            type=ftype,
            required=bool(d.get("required", False)),
            unique=bool(d.get("unique", False)),
            min=d.get("min"),
            max=d.get("max"),
            pattern=pattern,
            values=tuple(str(v) for v in d.get("values", ())),
            format=str(d.get("format", "%Y-%m-%d")),
            regex=regex,
        )


@dataclass(frozen=True)
class Schema:
    fields: tuple[Field, ...]
    primary_key: str | None = None
    allow_extra_columns: bool = False

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.fields]

    def __post_init__(self) -> None:
        if not self.fields:
            raise SchemaError("schema has no fields")
        dupes = {n for n in self.names if self.names.count(n) > 1}
        if dupes:
            raise SchemaError(f"duplicate field names: {', '.join(sorted(dupes))}")
        if self.primary_key is not None and self.primary_key not in self.names:
            raise SchemaError(f"primary_key '{self.primary_key}' is not a declared field")

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Schema":
        if not isinstance(d, dict) or not isinstance(d.get("fields"), list):
            raise SchemaError("schema must be an object with a 'fields' list")
        return Schema(
            fields=tuple(Field.from_dict(f) for f in d["fields"]),
            primary_key=d.get("primary_key"),
            allow_extra_columns=bool(d.get("allow_extra_columns", False)),
        )

    @staticmethod
    def load(path: str | Path) -> "Schema":
        try:
            with open(path, encoding="utf-8") as fh:
                return Schema.from_dict(json.load(fh))
        except json.JSONDecodeError as e:
            raise SchemaError(f"{path}: not valid JSON ({e.msg} at line {e.lineno})") from e
