# datalint

Validate a CSV file against a declared schema and get back three things: the rows that passed (normalized),
the rows that failed (with the exact reason, original values preserved), and a reconciliation summary
that always adds up. Pure Python, no dependencies.

I wrote it because every data task I touched started with the same question: "can I trust this file?"
The answer should be reproducible and auditable, not a one-off script.

## What it checks

| Rule             | Schema key                 | Issue code                                   |
| ---------------- | -------------------------- | -------------------------------------------- |
| Required         | `"required": true`         | `missing`                                    |
| Type             | `"type": int/float/bool/date/enum/string` | `not_int`, `not_float`, `not_bool`, `bad_date`, `not_in_enum` |
| Range            | `"min"`, `"max"`           | `below_min`, `above_max`                     |
| Pattern          | `"pattern": "<regex>"`     | `pattern`                                    |
| Uniqueness       | `"unique": true`           | `duplicate` (points back to the first row)   |
| Column presence  | declared fields vs header  | `missing_column`, `unexpected_column`        |

Rules that matter for trust:

- **Nothing is dropped silently.** Every input row lands in either `clean.csv` or `exceptions.csv`, and `rows_passed + rows_failed == rows_read` by construction.
- **Raw values are preserved** in the exceptions file so a reviewer sees what was actually in the source.
- **Normalization is deterministic:** trimmed strings, `1,250.00` to `1250.0`, `yes/TRUE/1` to `true`, dates to ISO.
- **An invalid value is never counted as a duplicate**, so one bad cell produces one issue, not two.

## Install and run

```bash
pip install -e ".[dev]"
datalint validate --schema examples/customers.schema.json --input examples/customers.csv --out-dir out
```

Output for the bundled example:

```
rows read:    9
rows passed:  3
rows failed:  6
issues:       8  (bad_date=1, below_min=1, duplicate=2, missing=1, not_bool=1, not_in_enum=1, pattern=1)
  row 3: 'email' value 'not-an-email' does not match pattern ^[^@\s]+@[^@\s]+\.[^@\s]+$
  row 4: 'plan' value 'platinum' is not a valid enum (expected one of: free, pro, enterprise)
  row 5: 'full_name' is required
  row 5: 'monthly_spend' value -20.0 is below minimum 0
  row 5: 'signed_up' value '06/15/2025' is not a valid date (expected format %Y-%m-%d)
  row 6: 'customer_id' value 2 already appeared on row 2
  row 7: 'email' value 'ana@example.com' already appeared on row 1
  row 8: 'active' value 'maybe' is not a valid bool
RESULT: FAIL
```

`--json` prints the summary as JSON for scripting. Exit codes: `0` all rows passed, `1` some rows or columns failed, `2` bad usage or schema.

Files written to `--out-dir`:

- `clean.csv`: passing rows, normalized, columns in schema order
- `exceptions.csv`: one line per issue with `row, field, code, message` plus the original row values
- `summary.json`: counts by status, by issue code, and by field

## Schema format

```json
{
  "primary_key": "customer_id",
  "allow_extra_columns": false,
  "fields": [
    { "name": "customer_id", "type": "int", "required": true, "unique": true, "min": 1 },
    { "name": "email", "type": "string", "required": true, "unique": true, "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$" },
    { "name": "plan", "type": "enum", "values": ["free", "pro", "enterprise"] },
    { "name": "monthly_spend", "type": "float", "min": 0, "max": 100000 },
    { "name": "active", "type": "bool" },
    { "name": "signed_up", "type": "date", "format": "%Y-%m-%d" }
  ]
}
```

A malformed schema (unknown type, enum without values, regex that does not compile, duplicate field names,
primary key that is not a field) is rejected with a clear message before any data is read.

## Tests

```bash
pytest -q
```

27 tests cover schema parsing errors, every issue code, normalization, duplicate tracking, file-level column
checks, report contents, and CLI exit codes. The example CSV is itself a fixture: the test asserts the exact
reconciliation counts shown above.

## Layout

```
src/datalint/
  schema.py     schema model + validation of the schema itself
  validate.py   pure row validation (no I/O)
  report.py     reconciliation summary, clean/exceptions/summary writers, text formatter
  cli.py        argparse entry point and exit codes
examples/       customers.schema.json, customers.csv
tests/          test_schema.py, test_validate.py, test_cli.py
```

## Limitations

- CSV input only. Reading JSON or Excel would mean adding a reader in `cli.py`; validation is format-agnostic.
- Files are loaded into memory. Fine for hundreds of thousands of rows, not for multi-gigabyte files.
- No cross-field rules yet (for example, `end_date >= start_date`).
