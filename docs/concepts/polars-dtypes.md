# Polars data types and schemas

Every column has one data type (dtype). The **schema** is the list of column names and their dtypes.

| dtype | Used for | Note |
|---|---|---|
| `Int64` | `id`, counts, day counts | GitHub ids don't fit in 32 bits |
| `Float64` | `star_fork_ratio` | dividing two integers gives a float |
| `String` | names, language, license | |
| `Boolean` | `fork`, `archived`, `disabled` | |
| `List(String)` | `topics` | each cell holds a list |
| `Datetime("us", "UTC")` | `created_at`, `updated_at`, `pushed_at` | microsecond precision, aware of the UTC time zone |
| `Date` | `snapshot_date` | a calendar day, no time |

## Explicit schema vs inference

`pl.DataFrame(rows)` without a schema **infers** the types by looking at the data. With real API data, the guess can go wrong:

- If every repo in a run has `"license": null`, the column has nothing to infer from and gets the `Null` type. The next step, which expects text, then fails.
- Nested objects (`owner` has around 20 sub-fields) become `Struct` columns you don't want.

So `transform.to_frame()` does two things:
1. `_select_fields()` picks the 15 needed fields in plain Python and flattens the nested ones (`owner.login` becomes `owner_login`).
2. `pl.DataFrame(rows, schema=RAW_SCHEMA)` builds the table with exactly the types listed in `RAW_SCHEMA`.

The result has the same columns and types every day, even for an empty list. The test `test_to_frame_has_exact_columns_and_types` checks it.

The output has a fixed column list too: `OUTPUT_COLUMNS` in `transform.py` matches the `CREATE TABLE` in `load.py`. The column list acts as a **contract** between the two steps.

## null and NaN

- `null` means "missing" and can appear in any column.
- `NaN` ("not a number") is a real floating-point value, produced for example by `0.0 / 0.0`.

Polars keeps the two apart. pandas mixes them up, which is one of the classic sources of bugs. `star_fork_ratio` uses `null` for "no forks", not `NaN` or `inf`.

## How the types travel

Polars → Arrow → DuckDB:

| Polars | DuckDB (`src/load.py`) | DuckDB (written by dlt) |
|---|---|---|
| `Int64` | `BIGINT` | `BIGINT` |
| `Float64` | `DOUBLE` | `DOUBLE` |
| `String` | `VARCHAR` | `VARCHAR` |
| `Boolean` | `BOOLEAN` | `BOOLEAN` |
| `Date` | `DATE` | `DATE` |
| `Datetime("us", "UTC")` | `TIMESTAMPTZ` | `TIMESTAMPTZ` |
| `List(String)` | `VARCHAR[]` | `JSON` |

The last row is a real difference between the two engines. `load.py` declares `topics VARCHAR[]` itself, while dlt chooses its own type for nested data and picks `JSON`.

## Read more

- https://docs.pola.rs/user-guide/concepts/data-types-and-structures/
- https://duckdb.org/docs/sql/data_types/overview
