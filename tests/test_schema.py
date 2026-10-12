import json

import pytest

from datalint.schema import Field, Schema, SchemaError


def test_loads_valid_schema(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"primary_key": "id", "fields": [{"name": "id", "type": "int", "unique": True}]}))
    s = Schema.load(p)
    assert s.names == ["id"]
    assert s.primary_key == "id"
    assert s.fields[0].unique is True


@pytest.mark.parametrize(
    "doc, msg",
    [
        ({}, "'fields' list"),
        ({"fields": []}, "no fields"),
        ({"fields": [{"type": "int"}]}, "non-empty 'name'"),
        ({"fields": [{"name": "x", "type": "money"}]}, "unknown type"),
        ({"fields": [{"name": "x", "type": "enum"}]}, "non-empty 'values'"),
        ({"fields": [{"name": "x", "type": "string", "min": 1}]}, "only applies to int or float"),
        ({"fields": [{"name": "x", "pattern": "("}]}, "invalid pattern"),
        ({"fields": [{"name": "x"}, {"name": "x"}]}, "duplicate field names"),
        ({"primary_key": "nope", "fields": [{"name": "x"}]}, "not a declared field"),
    ],
)
def test_rejects_malformed_schema(doc, msg):
    with pytest.raises(SchemaError, match=msg):
        Schema.from_dict(doc)


def test_invalid_json_is_a_schema_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(SchemaError, match="not valid JSON"):
        Schema.load(p)


def test_field_defaults():
    f = Field.from_dict({"name": "n"})
    assert (f.type, f.required, f.unique, f.format) == ("string", False, False, "%Y-%m-%d")
