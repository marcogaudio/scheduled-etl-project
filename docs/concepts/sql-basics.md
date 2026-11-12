# SQL basics

SQL statements come in three families:

| Family | Purpose | In `src/load.py` |
|---|---|---|
| **DDL** (data definition) | define structure | `CREATE TABLE IF NOT EXISTS repo_snapshots (...)`, `CREATE OR REPLACE VIEW repos_latest AS ...` |
| **DML** (data manipulation) | change data | `DELETE FROM ...`, `INSERT INTO ... BY NAME SELECT ...` |
| **Queries** | read data | `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...` |

Plus transaction control: `BEGIN TRANSACTION`, `COMMIT`, `ROLLBACK` (see [transactions](transactions.md)).

## A query, clause by clause

```sql
SELECT snapshot_date, count(*) AS repos   -- columns to return (dplyr: select / summarise)
FROM repo_snapshots                       -- which table
WHERE archived = false                    -- keep rows (dplyr: filter)
GROUP BY snapshot_date                    -- one output row per date (dplyr: group_by)
ORDER BY snapshot_date                    -- sort (dplyr: arrange)
```

SQL is written in that order, but the database evaluates it as `FROM`, `WHERE`, `GROUP BY`, `SELECT`, `ORDER BY`. That's why a column alias defined in `SELECT` can't be used in `WHERE`.

## Pieces used in this repo

- **Constraints**: `NOT NULL` on `snapshot_date`, `id` and `full_name` makes the database reject rows without them.
- **View**: `repos_latest` is a saved query, not a copy of the data. Selecting from it always shows the newest day.
- **Subquery**: `WHERE snapshot_date = (SELECT max(snapshot_date) FROM repo_snapshots)` computes the latest date inside the query.
- **`INSERT INTO t BY NAME SELECT * FROM incoming`**: matches columns by name rather than position, so a different column order can't put values into the wrong columns. A column the table doesn't have is an error.
- **No primary key**: the table could declare `PRIMARY KEY (id, snapshot_date)`, but DuckDB enforces keys with an index that slows bulk loading. Uniqueness comes from the delete-then-insert logic instead, and `test_no_duplicate_keys_after_reruns` checks it.

## Values as parameters, never pasted in

```python
con.execute("SELECT * FROM repo_snapshots WHERE full_name = ?", [name])   # safe
con.execute(f"SELECT * FROM repo_snapshots WHERE full_name = '{name}'")   # don't
```

Pasting a value into the SQL text lets that value rewrite the statement: a name like `x' OR '1'='1` changes the query. That's **SQL injection**. Parameters (`?`) are sent separately and are always treated as data. The f-strings in `load.py` only insert the module's own constants (table names), which can't be parameters.

## Window functions

A window function computes a value for each row from neighbouring rows, without collapsing the rows like `GROUP BY` does:

```sql
SELECT snapshot_date, full_name, stargazers_count,
       stargazers_count - lag(stargazers_count) OVER (PARTITION BY id ORDER BY snapshot_date) AS stars_gained
FROM github.repo_snapshots
```

- `PARTITION BY id` restarts the window for each repository.
- `ORDER BY snapshot_date` defines what "previous" means, and `lag()` reads the previous row.

It's the same calculation as a daily return on a price series. Note that `lag(x, 7)` means 7 *rows* back, not 7 days: if a day is missing, it reaches further.

## Read more

- https://duckdb.org/docs/sql/introduction
- https://duckdb.org/docs/sql/statements/insert
- https://duckdb.org/docs/sql/functions/window_functions
- https://owasp.org/www-community/attacks/SQL_Injection
