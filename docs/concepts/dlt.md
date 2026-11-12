# dlt

dlt ("data load tool", from dltHub) is an open-source Python library that automates the repetitive parts of moving data from an API into a database: HTTP calls, pagination, retries, creating tables, changing them when new columns appear, and loading safely.

This repo has the same extract and load written twice, to make clear what dlt automates:

| Job | By hand | With dlt (`dlt_pipeline/pipeline.py`) |
|---|---|---|
| headers, auth, retries | `make_session()` | `RESTClient(..., auth=BearerTokenAuth(token))` |
| pagination | `paginate()` | `HeaderLinkPaginator()` + `client.paginate()` |
| create the table | `CREATE TABLE` written in SQL | inferred from the data |
| new columns later | `ALTER TABLE` by hand | added automatically (schema evolution) |
| re-run safety | delete + insert in a transaction | `write_disposition="merge"` + `primary_key` |
| another database | rewrite `load.py` | change `destination=` |

The transform is shared: both engines call `src/transform.py`.

## Vocabulary

- **Resource**: a generator decorated with `@dlt.resource`; it yields data and becomes one table. `repo_snapshots(df)` yields the transformed DataFrame as an Arrow table.
- **Source**: a group of resources from the same system. Not needed with a single resource.
- **Pipeline**: moves data from resources to a destination. Built in `make_pipeline()` with `pipeline_name="github_etl"`.
- **Destination**: where the data goes: `dlt.destinations.duckdb("data/output.duckdb")`.
- **Dataset**: dlt's name for a group of tables. In DuckDB it becomes a schema, here `github`.
- **State**: values dlt remembers between runs, such as the cursor for incremental loading. Not used here yet.

## What `pipeline.run()` does

1. **Extract**: pulls items from the resource and writes them to local files.
2. **Normalize**: works out the schema (column names and types) and prepares load files. Nested data gets flattened into child tables or JSON columns.
3. **Load**: creates or alters the tables, writes the rows, and records the load in `_dlt_loads`.

It returns a `LoadInfo` summary. `load_info.raise_on_failed_jobs()` turns a failed load into an exception, so the run fails loudly.

## Where things end up

- Tables, in the `github` schema of the same DuckDB file: `repo_snapshots`, `_dlt_loads` (one row per run), `_dlt_pipeline_state`, `_dlt_version`. `github_staging` holds temporary tables used during a merge.
- Working files: `~/.dlt/pipelines/github_etl/`. On a fresh machine such as a GitHub Actions runner, dlt restores its state from `_dlt_pipeline_state` in the database.
- dlt picks its own column types. `topics` becomes `JSON` here, while `src/load.py` declares `VARCHAR[]`. Compare `DESCRIBE github.repo_snapshots` with `DESCRIBE main.repo_snapshots`.

```bash
dlt pipeline github_etl info      # what the last run did
```

## Gotchas

- Don't name a folder `dlt/` in the project: it hides the library. See [entry points](entry-points.md).
- Tests pass `pipelines_dir=tmp_path / "dlt"` so dlt's working files don't end up in your home folder.
- When yielding Arrow tables, dlt may log a warning that "column hints were different". It's informational: dlt keeps its own hints (such as primary key columns being NOT NULL) and the data is unchanged.

## Read more

- https://dlthub.com/docs/intro
- https://dlthub.com/docs/general-usage/resource
- https://dlthub.com/docs/general-usage/pipeline
- https://dlthub.com/docs/general-usage/http/rest-client
