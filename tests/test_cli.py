import csv
import json
from pathlib import Path

from datalint.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_example_file_fails_with_expected_reconciliation(tmp_path, capsys):
    out = tmp_path / "out"
    code = main(["validate", "--schema", str(EXAMPLES / "customers.schema.json"), "--input", str(EXAMPLES / "customers.csv"), "--out-dir", str(out), "--json"])
    assert code == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary["rows_read"] == 9
    assert summary["rows_passed"] == 3
    assert summary["rows_failed"] == 6
    assert summary["issues_by_code"] == {
        "bad_date": 1,
        "below_min": 1,
        "duplicate": 2,
        "missing": 1,
        "not_bool": 1,
        "not_in_enum": 1,
        "pattern": 1,
    }
    # passed + failed always reconciles to rows read
    assert summary["rows_passed"] + summary["rows_failed"] == summary["rows_read"]

    clean = list(csv.DictReader(open(out / "clean.csv", encoding="utf-8")))
    assert [r["customer_id"] for r in clean] == ["1", "2", "8"]
    assert clean[0]["monthly_spend"] == "1250.0" and clean[0]["active"] == "true"

    exceptions = list(csv.DictReader(open(out / "exceptions.csv", encoding="utf-8")))
    assert len(exceptions) == summary["issues_total"]
    assert {e["row"] for e in exceptions} == {"3", "4", "5", "6", "7", "8"}
    # raw values are preserved in the exceptions file
    assert any(e["signed_up"] == "06/15/2025" for e in exceptions)

    assert json.loads((out / "summary.json").read_text()) == summary


def test_text_output_and_pass_exit_code(tmp_path, capsys):
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps({"fields": [{"name": "id", "type": "int", "required": True}]}))
    data = tmp_path / "d.csv"
    data.write_text("id\n1\n2\n")
    assert main(["validate", "--schema", str(schema), "--input", str(data)]) == 0
    out = capsys.readouterr().out
    assert "rows passed:  2" in out and out.strip().endswith("RESULT: PASS")


def test_bad_schema_exits_2(tmp_path, capsys):
    schema = tmp_path / "s.json"
    schema.write_text("{}")
    data = tmp_path / "d.csv"
    data.write_text("id\n1\n")
    assert main(["validate", "--schema", str(schema), "--input", str(data)]) == 2
    assert "schema error" in capsys.readouterr().err


def test_missing_input_exits_2(tmp_path, capsys):
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps({"fields": [{"name": "id"}]}))
    assert main(["validate", "--schema", str(schema), "--input", str(tmp_path / "nope.csv")]) == 2
    assert "input error" in capsys.readouterr().err


def test_empty_file_reports_missing_columns(tmp_path, capsys):
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps({"fields": [{"name": "id"}]}))
    data = tmp_path / "d.csv"
    data.write_text("")
    assert main(["validate", "--schema", str(schema), "--input", str(data)]) == 1
    assert "missing_column" not in capsys.readouterr().out  # text mode prints the message, not the code
