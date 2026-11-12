# Snapshot tables

A **periodic snapshot table** stores the state of every entity once per period. Here: one row per repository per day. The **grain** of the table, what one row represents, is *(repository, day)*, identified by `(id, snapshot_date)`.

```
snapshot_date | id | full_name      | stargazers_count
2026-10-29    | 1  | pola-rs/polars | 1500
2026-10-30    | 1  | pola-rs/polars | 1507     <- a new slice every day
2026-10-31    | 1  | pola-rs/polars | 1511
```

## Why snapshots

The GitHub API only says how many stars a repository has **now**. There's no way to ask for last Tuesday's number. To study change over time (growth per day or week, which project is accelerating), the job has to record the state every day. A missed day is lost for good.

## The two load modes

| `load.mode` | One run does | History |
|---|---|---|
| `append` (default) | replaces only today's slice | kept |
| `overwrite` | replaces the whole table with today | only today remains |

`main.repos_latest` is a view showing only the newest slice, for "what does it look like now" questions.

## Alternatives

- **Overwrite only**: just the current state, the simplest option. Fine when history doesn't matter.
- **Slowly changing dimension, type 2 (SCD2)**: one row per *version* of an entity, with `valid_from` and `valid_to` dates. A new row is added only when something changed. That's more compact when values rarely change, but harder to query. Star counts change daily, so snapshots fit better.
- **Event table**: store each change as an event, like "starred at 10:42". GitHub doesn't give us that for stars.

## Size

Rows = repositories × days. Six repositories for a year is about 2,200 rows: nothing. A thousand repositories for five years is about 1.8 million: still small for DuckDB.

## Partitioning

`load.export_parquet()` (not called by the daily run) writes the table as Parquet files, one folder per day:

```
data/parquet/snapshot_date=2026-10-31/data_0.parquet
```

This is **Hive-style partitioning**. Tools like Polars, Spark and BigQuery read the folder name as a column and skip the folders a query doesn't need. It's useful once the data outgrows one file, or when other tools need to read it.

## Read more

- https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/periodic-snapshot-fact-table/
- https://duckdb.org/docs/data/partitioning/hive_partitioning
