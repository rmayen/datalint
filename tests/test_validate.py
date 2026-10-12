from datetime import date

from datalint.schema import Schema
from datalint.validate import validate_rows

SCHEMA = Schema.from_dict(
    {
        "fields": [
            {"name": "id", "type": "int", "required": True, "unique": True, "min": 1},
            {"name": "email", "type": "string", "required": True, "pattern": "^[^@]+@[^@]+$"},
            {"name": "plan", "type": "enum", "values": ["free", "pro"]},
            {"name": "spend", "type": "float", "min": 0, "max": 100},
            {"name": "active", "type": "bool"},
            {"name": "joined", "type": "date"},
        ]
    }
)
HEADER = SCHEMA.names


def row(**kw):
    base = {"id": "1", "email": "a@b.c", "plan": "pro", "spend": "10", "active": "yes", "joined": "2025-01-02"}
    base.update(kw)
    return base


def codes(results):
    return sorted(i.code for r in results for i in r.issues)


def test_clean_row_passes_and_is_normalized():
    results, file_issues = validate_rows(SCHEMA, [row(spend=" 12.5 ", active="TRUE")], HEADER)
    assert file_issues == []
    assert results[0].ok
    assert results[0].normalized == {"id": 1, "email": "a@b.c", "plan": "pro", "spend": 12.5, "active": True, "joined": date(2025, 1, 2)}


def test_missing_required_and_optional_blank():
    results, _ = validate_rows(SCHEMA, [row(email="", spend="", plan="")], HEADER)
    assert codes(results) == ["missing"]
    assert results[0].issues[0].field == "email"
    assert results[0].normalized["spend"] is None


def test_type_errors_are_reported_per_field():
    results, _ = validate_rows(SCHEMA, [row(id="x", spend="lots", active="maybe", joined="01/02/2025", plan="gold")], HEADER)
    assert codes(results) == ["bad_date", "not_bool", "not_float", "not_in_enum", "not_int"]
    assert "expected one of: free, pro" in next(i.message for i in results[0].issues if i.code == "not_in_enum")


def test_float_accepts_thousands_separators():
    results, _ = validate_rows(SCHEMA, [row(spend="99.5")], HEADER)
    assert results[0].normalized["spend"] == 99.5
    results, _ = validate_rows(SCHEMA, [row(spend="1,000")], HEADER)
    assert results[0].normalized["spend"] == 1000.0 and codes(results) == ["above_max"]


def test_range_and_pattern_checks():
    results, _ = validate_rows(SCHEMA, [row(id="0", email="nope", spend="250")], HEADER)
    assert codes(results) == ["above_max", "below_min", "pattern"]


def test_duplicates_point_back_to_first_occurrence():
    results, _ = validate_rows(SCHEMA, [row(id="7"), row(id="8"), row(id="7")], HEADER)
    assert [r.ok for r in results] == [True, True, False]
    dup = results[2].issues[0]
    assert dup.code == "duplicate" and "row 1" in dup.message


def test_invalid_value_is_not_counted_as_duplicate():
    results, _ = validate_rows(SCHEMA, [row(id="x"), row(id="x")], HEADER)
    assert codes(results) == ["not_int", "not_int"]


def test_missing_and_unexpected_columns_are_file_level():
    header = ["id", "email", "plan", "spend", "active", "extra"]
    _, file_issues = validate_rows(SCHEMA, [], header)
    assert sorted(i.code for i in file_issues) == ["missing_column", "unexpected_column"]


def test_extra_columns_allowed_when_schema_says_so():
    s = Schema.from_dict({"allow_extra_columns": True, "fields": [{"name": "id", "type": "int"}]})
    _, file_issues = validate_rows(s, [], ["id", "note"])
    assert file_issues == []


def test_rows_are_never_dropped():
    rows = [row(id=str(i)) for i in range(1, 6)] + [row(id="bad")]
    results, _ = validate_rows(SCHEMA, rows, HEADER)
    assert len(results) == 6
    assert sum(r.ok for r in results) == 5
