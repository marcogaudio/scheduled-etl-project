# DuckDB

DuckDB is an **embedded analytical database**:
- **Embedded**: there's no server to install or start. It's a library running inside your Python process (`import duckdb`), and the whole database is one file, `data/output.duckdb`.
- **Analytical (OLAP)**: it's built for questions that scan many rows and aggregate them, like "average stars per language" or "stars gained per repo per day".

It's often described as "SQLite for analytics".

## OLTP vs OLAP

| | OLTP (PostgreSQL, SQLite, MySQL) | OLAP (DuckDB, BigQuery, Snowflake) |
|---|---|---|
| Typical work | many small reads/writes of single rows (orders, logins) | few big queries over many rows |
| Storage | row by row | **column by column** |
| Strength | fast inserts and updates, lots of concurrent users | fast scans, aggregations, compression |

Columnar storage keeps all the values of one column together. A query that needs 2 columns out of 19 reads only those 2, and similar values next to each other compress well. DuckDB also processes values in batches (**vectorised execution**) instead of one row at a time.

## How the repo uses it (`src/load.py`)

```python
with connect(db_path) as con:               # duckdb.connect(), creates the file if missing
    ensure_schema(con)                      # CREATE TABLE IF NOT EXISTS / CREATE OR REPLACE VIEW
    write_snapshot(con, df, mode)           # DELETE + INSERT inside a transaction
```

- `con.register("incoming", df)` makes the Polars DataFrame visible to SQL under a name. DuckDB reads it through [Arrow](apache-arrow.md), without converting it row by row.
- `con.sql("SELECT ...").pl()` returns any query result as a Polars DataFrame; `.df()` gives pandas and `.fetchall()` Python tuples.
- A DuckDB file can hold several **schemas** (namespaces): the hand-written engine writes to `main`, dlt writes to `github`.

## One writer at a time

A DuckDB file can be opened by **one process for writing**, or by **several processes read-only** (`duckdb.connect(path, read_only=True)`). While a DBeaver window or a notebook holds a write connection, the pipeline fails with `Could not set lock on file`. Close connections when you're done; a `with` block does it for you.

## Exploring the file

```python
import duckdb
con = duckdb.connect("data/output.duckdb", read_only=True)
con.sql("SHOW ALL TABLES")
con.sql("DESCRIBE main.repo_snapshots")
con.sql("SELECT * FROM main.repos_latest ORDER BY stargazers_count DESC")
```

There's also a command-line tool (`duckdb data/output.duckdb`), installed separately from the Python package. DuckDB can query Parquet and CSV files directly too: `SELECT * FROM 'file.parquet'`.

## Read more

- https://duckdb.org/docs/api/python/overview
- https://duckdb.org/docs/connect/concurrency
- https://duckdb.org/why_duckdb
