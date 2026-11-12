# Apache Arrow

Apache Arrow is a standard for laying out table data **in memory**, column by column. Polars, DuckDB, dlt, pandas (optionally) and Spark all understand it. When two libraries use the same layout, one can read the other's data directly instead of converting it value by value.

## Why it matters

Without a shared format, handing a table from library A to library B means walking through every value and rebuilding it in B's format. That's slow and doubles the memory. With Arrow, B can often read A's buffers as they are: a **zero-copy** hand-off.

## Where it happens in this repo

| Code | Hand-off |
|---|---|
| `con.register("incoming", df)` in `load.write_snapshot()` | DuckDB reads the Polars DataFrame through Arrow |
| `con.sql(...).pl()` | DuckDB hands a result back to Polars |
| `yield df.to_arrow()` in `dlt_pipeline.repo_snapshots()` | dlt receives a `pyarrow.Table` and loads it in bulk, keeping the column types |

`pyarrow`, the Python implementation, is in `requirements.txt` because those hand-offs need it.

When dlt receives Arrow tables, it uses its fast path: it doesn't inspect rows one by one, and it doesn't add its `_dlt_id` / `_dlt_load_id` columns to the table. Each load is still recorded in `github._dlt_loads`.

## Arrow vs Parquet

Both are columnar, for different places:
- **Arrow**: in memory, built for fast processing and exchange between programs
- **Parquet**: on disk, compressed, built for storage

Reading Parquet usually means decoding it into Arrow. `load.export_parquet()` writes Parquet.

## Read more

- https://arrow.apache.org/overview/
- https://arrow.apache.org/docs/python/
