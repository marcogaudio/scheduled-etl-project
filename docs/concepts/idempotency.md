# Idempotency

An operation is **idempotent** when doing it twice has the same effect as doing it once. Pressing a lift's call button is idempotent; adding 10 € to an account is not.

## Why a scheduled job needs it

The daily ETL will sometimes run more than once on the same day:
- GitHub Actions re-runs a failed job.
- Someone clicks "Run workflow" on a day the schedule already ran.
- You run `python -m src.main` twice while testing.

If each run *adds* rows, every extra run creates duplicates, and every chart built on the table quietly doubles. An idempotent load makes re-running safe.

## How this repo does it

**Hand-written engine (`load.write_snapshot`)**: delete the dates being loaded, then insert, inside one [transaction](transactions.md):

```sql
DELETE FROM repo_snapshots WHERE snapshot_date IN (SELECT DISTINCT snapshot_date FROM incoming);
INSERT INTO repo_snapshots BY NAME SELECT * FROM incoming;
```

Run it once or ten times on the same day: today still has one row per repository, and older days are untouched. This pattern is often called *delete-insert* or *replace partition*.

**dlt engine (`load_with_dlt`)**: `write_disposition="merge"` with `primary_key=("id", "snapshot_date")`. Rows with a key that already exists are updated instead of added. See [write dispositions](dlt-write-dispositions.md).

The two aren't identical. Delete-insert replaces the *whole day*, while merge updates *row by row*. If a repository disappeared from the config between two runs on the same day, merge would keep its morning row and delete-insert would not.

## What breaks it

- A plain `INSERT`, or dlt's `append` disposition.
- Reading the clock in several places: two runs straddling midnight would write to different days. One `as_of` per run avoids that.
- An empty result in `overwrite` mode would wipe the history. That's why `write_snapshot()` and `load_with_dlt()` refuse to load zero rows.

## Tests

- `test_rerun_on_the_same_day_is_idempotent`
- `test_no_duplicate_keys_after_reruns`
- `test_same_day_rerun_is_idempotent` (dlt)

## Read more

- https://en.wikipedia.org/wiki/Idempotence
