# Study notes

Each note in `concepts/` covers one idea used in this project. Every note has four parts:
- what the idea is
- where it appears in the code
- the mistakes worth remembering
- where to read more

Comments in the code point to them as `Concept: docs/concepts/<name>.md`.

The order below follows the code, from `src/config.py` to the workflow files. Unfamiliar terms are defined in the [glossary](glossary.md).

## The big picture
- [ETL](concepts/etl.md)

## Python project basics
- [Virtual environments and dependencies](concepts/virtual-environments.md)
- [Modules, packages and entry points](concepts/entry-points.md)
- [Environment variables and secrets](concepts/environment-variables.md)
- [TOML configuration](concepts/toml-tomllib.md)
- [pathlib](concepts/pathlib.md)
- [Dataclasses and type hints](concepts/dataclasses.md)
- [Logging](concepts/logging.md)
- [Command-line options with argparse](concepts/argparse.md)
- [Exit codes and error handling](concepts/exit-codes.md)

## Extract
- [HTTP and REST APIs](concepts/http-rest.md)
- [requests: sessions, timeouts, retries](concepts/requests-session.md)
- [Pagination](concepts/pagination.md)
- [Rate limiting and backoff](concepts/rate-limiting.md)
- [Generators](concepts/generators.md)

## Transform
- [Polars DataFrames, eager and lazy](concepts/polars-dataframe.md)
- [Polars data types and schemas](concepts/polars-dtypes.md)
- [Polars expressions](concepts/polars-expressions.md)
- [Dates, times and time zones](concepts/datetimes-timezones.md)
- [Pure functions](concepts/pure-functions.md)

## Load
- [DuckDB](concepts/duckdb.md)
- [SQL basics](concepts/sql-basics.md)
- [Transactions](concepts/transactions.md)
- [Idempotency](concepts/idempotency.md)
- [Snapshot tables](concepts/snapshot-tables.md)
- [Apache Arrow](concepts/apache-arrow.md)

## dlt
- [dlt](concepts/dlt.md)
- [Write dispositions](concepts/dlt-write-dispositions.md)

## Testing
- [pytest](concepts/pytest.md)
- [Fixtures](concepts/pytest-fixtures.md)
- [monkeypatch](concepts/monkeypatch.md)
- [Faking HTTP in tests](concepts/mocking-http.md)

## Automation
- [GitHub Actions, YAML and cron](concepts/github-actions.md)
