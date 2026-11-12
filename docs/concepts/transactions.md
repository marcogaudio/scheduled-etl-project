# Transactions

A **transaction** groups several statements into one unit: either all of them take effect, or none do.

```sql
BEGIN TRANSACTION;
DELETE FROM repo_snapshots WHERE snapshot_date IN (SELECT DISTINCT snapshot_date FROM incoming);
INSERT INTO repo_snapshots BY NAME SELECT * FROM incoming;
COMMIT;      -- both changes become visible together
-- or
ROLLBACK;    -- both changes are undone, as if nothing happened
```

Without `BEGIN`, DuckDB runs every statement in its own small transaction (autocommit).

## Why the load needs one

`write_snapshot()` first deletes today's rows, then inserts the new ones. Suppose the `INSERT` fails: a column that doesn't exist, a full disk, a crash. Without a transaction, the `DELETE` has already happened, and today's data is simply gone.

With a transaction:

```python
con.execute("BEGIN TRANSACTION")
try:
    ...DELETE...
    ...INSERT...
    con.execute("COMMIT")
except Exception:
    con.execute("ROLLBACK")   # the deleted rows come back
    raise                     # the run still fails loudly
finally:
    con.unregister(INCOMING)  # runs in both cases
```

`test_failed_insert_rolls_back_the_delete` proves it. It loads a day, then loads a DataFrame with an extra unknown column, so the `INSERT` fails after the `DELETE` has run. Afterwards the original two rows are still there.

## ACID

The four guarantees a database gives for transactions:

| Letter | Guarantee | Here |
|---|---|---|
| **A**tomicity | all or nothing | delete + insert can't half-happen |
| **C**onsistency | constraints hold before and after | `NOT NULL` columns are never empty |
| **I**solation | others don't see a half-finished transaction | a reader never sees a day with 0 rows mid-load |
| **D**urability | after `COMMIT`, the data survives a crash | the file on disk has the new rows |

## Read more

- https://duckdb.org/docs/sql/statements/transactions
- https://en.wikipedia.org/wiki/ACID
