# Glossary

**API**: an interface one program offers to another. Here, GitHub's web API, which answers HTTP requests with JSON. See [HTTP and REST](concepts/http-rest.md).

**Apache Arrow**: a standard way to lay out columnar data in memory, shared by Polars, DuckDB and dlt. See [Apache Arrow](concepts/apache-arrow.md).

**Artifact**: a file uploaded by a GitHub Actions run, downloadable from the run page. See [GitHub Actions](concepts/github-actions.md).

**Backoff**: waiting longer and longer between retries of a failed request. See [rate limiting](concepts/rate-limiting.md).

**Batch job**: a program that processes a whole chunk of data at once, on a schedule, as opposed to streaming. See [ETL](concepts/etl.md).

**Cache (GitHub Actions)**: files one run saves so that later runs can restore them. This project uses it to carry the database from day to day.

**Columnar storage**: storing a table column by column instead of row by row, which makes scans and aggregations fast. See [DuckDB](concepts/duckdb.md).

**Cron expression**: five fields (minute, hour, day of month, month, day of week) describing a schedule. `17 6 * * *` means 06:17 every day.

**DataFrame**: a table of named columns, each with one data type. See [Polars DataFrames](concepts/polars-dataframe.md).

**Dataset (dlt)**: dlt's name for a group of tables. In DuckDB it becomes a schema, here `github`.

**DDL / DML**: the two families of SQL statements. DDL defines structure (`CREATE TABLE`); DML changes data (`INSERT`, `DELETE`). See [SQL basics](concepts/sql-basics.md).

**dlt**: a Python library that automates extracting data from APIs and loading it into databases. See [dlt](concepts/dlt.md).

**DuckDB**: an analytical database that runs inside your Python process and stores everything in one file. See [DuckDB](concepts/duckdb.md).

**dtype**: the data type of a column, such as `Int64`, `String` or `Datetime`. See [data types](concepts/polars-dtypes.md).

**ELT**: extract, load, then transform inside the database. The opposite order to ETL. See [ETL](concepts/etl.md).

**ETL**: extract, transform, load: the three steps of moving data from a source into a place where it can be analysed.

**Exit code**: the number a program hands back to the operating system when it ends. `0` means success. See [exit codes](concepts/exit-codes.md).

**Expression (Polars)**: a description of a column computation, such as `pl.col("a") / pl.col("b")`. Polars runs it later. See [expressions](concepts/polars-expressions.md).

**Fixture**: a pytest function that prepares something a test needs. See [fixtures](concepts/pytest-fixtures.md).

**Generator**: a function that uses `yield` to produce values one at a time, on demand. See [generators](concepts/generators.md).

**Idempotent**: an operation is idempotent if doing it twice gives the same result as doing it once. See [idempotency](concepts/idempotency.md).

**ISO 8601**: the standard text format for dates and times, e.g. `2026-10-30T18:55:01Z`. See [dates and times](concepts/datetimes-timezones.md).

**JSON**: a text format for nested data made of objects (`{}`), lists (`[]`), strings, numbers, booleans and `null`.

**Lazy evaluation**: describing all the work first and running it at the end, so the engine can optimise the whole plan.

**Mocking**: replacing a real dependency (the network, the clock) with a fake one during a test. See [faking HTTP](concepts/mocking-http.md).

**Null**: a missing value. `None` in Python, `NA` in R, `NULL` in SQL.

**OLAP / OLTP**: OLAP (analytical) databases are built for large scans and aggregations; OLTP (transactional) databases for many small reads and writes. DuckDB is OLAP; PostgreSQL and SQLite are OLTP.

**Pagination**: an API returning a long list in pages. See [pagination](concepts/pagination.md).

**Primary key**: the column or columns that identify a row. Here, `(id, snapshot_date)`.

**Pure function**: a function whose result depends only on its arguments and which changes nothing outside itself. See [pure functions](concepts/pure-functions.md).

**Rate limit**: the number of requests an API accepts in a given time window. See [rate limiting](concepts/rate-limiting.md).

**Resource (dlt)**: a generator decorated with `@dlt.resource`. Each resource becomes one table.

**REST**: a style of web API in which every thing has a URL and you use HTTP methods (`GET`, `POST`, …) on it.

**Runner**: the virtual machine that runs a GitHub Actions job. It's created fresh for every run.

**Schema**: either the list of columns and their types, or (in a database) a namespace that groups tables, like `main` and `github`.

**Snapshot table**: a table that stores the state of every entity once per period. See [snapshot tables](concepts/snapshot-tables.md).

**SQL injection**: an attack where text pasted into an SQL statement changes what the statement does. Avoided by passing values as parameters.

**Transaction**: a group of database statements that either all take effect or none do. See [transactions](concepts/transactions.md).

**Unix timestamp**: seconds since 1970-01-01 00:00:00 UTC. GitHub's `X-RateLimit-Reset` header uses it.

**UTC**: Coordinated Universal Time, the time zone without daylight saving. Every timestamp in this project is in UTC.

**View**: a saved query you can select from as if it were a table. `repos_latest` is one.

**Virtual environment**: a folder with its own Python packages, separate from the rest of the system. See [virtual environments](concepts/virtual-environments.md).

**Workflow**: a YAML file in `.github/workflows/` that tells GitHub Actions what to run and when.

**YAML**: an indentation-based text format for configuration, used by GitHub Actions.
