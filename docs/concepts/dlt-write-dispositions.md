# dlt write dispositions

A **write disposition** tells dlt what to do with rows from a new run when the table already has data.

| Disposition | What happens | Same-day re-run | Use for |
|---|---|---|---|
| `append` | new rows are added | duplicates | logs and events you never re-load |
| `replace` | the table is emptied, then loaded | fine | small tables you always reload whole |
| `merge` | rows whose primary key already exists are replaced, the rest are added | fine | anything re-runnable with a key |

## The mapping in this repo

```python
WRITE_DISPOSITIONS = {
    "append": "merge",      # our append mode = keep history, re-runs replace rows by key
    "overwrite": "replace",
}
```

The names don't line up, and that's on purpose. Our `append` mode means "add today, keep history, safe to re-run". dlt's `append` would duplicate today's rows on a second run, so it's mapped to `merge` with `primary_key=("id", "snapshot_date")`.

The decorator sets the default, and `pipeline.run(..., write_disposition=...)` overrides it for one run:

```python
@dlt.resource(name="repo_snapshots", write_disposition="merge", primary_key=("id", "snapshot_date"))
def repo_snapshots(df): ...

pipeline.run(repo_snapshots(df), write_disposition=WRITE_DISPOSITIONS[mode])
```

## How merge works

dlt's default merge strategy is **delete-insert**:
1. Load the new rows into a staging table (in the `github_staging` schema).
2. Delete the rows in the real table whose keys appear in staging.
3. Insert the staged rows.

It's the same idea as `src/load.py`, except that `load.py` deletes by `snapshot_date` (the whole day), while dlt deletes by `(id, snapshot_date)` (only the incoming rows). The difference shows up only if a repository vanishes between two runs on the same day: dlt keeps its morning row. See [idempotency](idempotency.md).

dlt also offers `scd2` (keep every version of a row with validity dates) and `upsert` merge strategies.

## Tests (`tests/test_dlt_pipeline.py`)

- `test_same_day_rerun_is_idempotent`: two merges on one day leave 2 rows, not 4
- `test_append_keeps_previous_days`: two days give 2 + 2 rows
- `test_overwrite_replaces_the_table`: replace leaves only the last day
- `test_empty_dataframe_is_not_loaded`: an empty `replace` would wipe history, so the code refuses it

## Read more

- https://dlthub.com/docs/general-usage/incremental-loading
- https://dlthub.com/docs/general-usage/merge-loading
