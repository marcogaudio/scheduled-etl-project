"""Load step: write the transformed repositories into a local DuckDB database.

Input:  the DataFrame from transform.py (columns = transform.OUTPUT_COLUMNS),
        the database path and the load mode from the settings.
Output: the table repo_snapshots and the view repos_latest in the DuckDB file.

Snapshot strategy: every run stores one row per repository for its
snapshot_date, so the table keeps the full daily history. Re-running on the
same day replaces that day's rows instead of duplicating them (idempotent).

Concepts: docs/concepts/duckdb.md, docs/concepts/sql-basics.md,
docs/concepts/transactions.md, docs/concepts/idempotency.md,
docs/concepts/snapshot-tables.md
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl

from src.config import PROJECT_ROOT, load_settings

logger = logging.getLogger(__name__)

TABLE = "repo_snapshots"
LATEST_VIEW = "repos_latest"
VALID_MODES = ("append", "overwrite")

# Name under which the incoming DataFrame is visible to SQL during a load.
INCOMING = "incoming"

# Explicit table definition: one column per transform.OUTPUT_COLUMNS entry.
# (snapshot_date, id) identifies a row; uniqueness is guaranteed by the
# delete-insert logic in write_snapshot() (see the plan, section 5.7).
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    snapshot_date        DATE        NOT NULL,
    id                   BIGINT      NOT NULL,
    full_name            VARCHAR     NOT NULL,
    owner_login          VARCHAR,
    language             VARCHAR,
    license_spdx         VARCHAR,
    stargazers_count     BIGINT,
    forks_count          BIGINT,
    open_issues_count    BIGINT,
    star_fork_ratio      DOUBLE,
    topics               VARCHAR[],
    fork                 BOOLEAN,
    archived             BOOLEAN,
    disabled             BOOLEAN,
    created_at           TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ,
    pushed_at            TIMESTAMPTZ,
    repo_age_days        BIGINT,
    days_since_last_push BIGINT
)
"""

# A view is a saved query: it always shows the most recent snapshot only.
CREATE_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {LATEST_VIEW} AS
SELECT *
FROM {TABLE}
WHERE snapshot_date = (SELECT max(snapshot_date) FROM {TABLE})
"""


def load(df: pl.DataFrame, db_path: Path, mode: str) -> int:
    """Write one run's DataFrame into the DuckDB file.

    This is the function main.py calls: it opens the database, makes sure the
    table and view exist, and writes the snapshot.

    Args:
        df: Output of transform.transform().
        db_path: Path of the DuckDB file (created if it does not exist).
        mode: "append" (replace only the DataFrame's dates, keep history)
            or "overwrite" (replace the whole table).

    Returns:
        The number of rows written.
    """
    # "with" closes the connection at the end, even if an error happens;
    # closing also releases the file lock so other tools can open the file.
    with connect(db_path) as con:
        ensure_schema(con)
        return write_snapshot(con, df, mode)


def connect(db_path: Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open (or create) the DuckDB database file.

    Args:
        db_path: Path of the .duckdb file.
        read_only: True to only read. Several read-only connections may be
            open at once, but only ONE process may write to the file.

    Returns:
        An open connection. Use it in a ``with`` block so it gets closed.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)  # create data/ if missing
    return duckdb.connect(str(db_path), read_only=read_only)


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create the snapshot table and the "latest" view if they don't exist yet.

    Safe to call on every run: IF NOT EXISTS / OR REPLACE make it a no-op
    when everything is already there.
    """
    con.execute(CREATE_TABLE_SQL)
    con.execute(CREATE_VIEW_SQL)


def write_snapshot(con: duckdb.DuckDBPyConnection, df: pl.DataFrame, mode: str) -> int:
    """Replace the affected rows with the DataFrame's rows, in one transaction.

    - mode="append":    delete the rows whose snapshot_date appears in df,
                        then insert df (re-running a day replaces that day).
    - mode="overwrite": delete every row, then insert df.

    If anything fails, the transaction is rolled back: the table is left
    exactly as it was before, and the error is raised.

    Args:
        con: Open, writable connection.
        df: Rows to write (columns must exist in the table).
        mode: "append" or "overwrite".

    Returns:
        The number of rows inserted (0 if df is empty).

    Raises:
        ValueError: If mode is not one of VALID_MODES.
        duckdb.Error: If the database rejects the data (e.g. an unknown column).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}.")
    if df.is_empty():
        # Protect the history: in overwrite mode an empty DataFrame would wipe the table.
        logger.warning("Nothing to load (0 rows): the table was left unchanged.")
        return 0

    # Make the Polars DataFrame visible to SQL under the name "incoming".
    # DuckDB reads it through Apache Arrow, with little or no copying.
    con.register(INCOMING, df)
    con.execute("BEGIN TRANSACTION")
    try:
        if mode == "overwrite":
            deleted = con.execute(f"DELETE FROM {TABLE}").fetchone()[0]
        else:
            # Only the dates being loaded are replaced; older days are untouched.
            deleted = con.execute(
                f"DELETE FROM {TABLE} WHERE snapshot_date IN (SELECT DISTINCT snapshot_date FROM {INCOMING})"
            ).fetchone()[0]
        # BY NAME: match columns by name, so column order cannot cause mix-ups.
        con.execute(f"INSERT INTO {TABLE} BY NAME SELECT * FROM {INCOMING}")
        con.execute("COMMIT")  # make both statements permanent, together
    except Exception:
        con.execute("ROLLBACK")  # undo the DELETE as well: nothing changed
        raise  # re-raise the original error so the run fails loudly
    finally:
        con.unregister(INCOMING)  # "finally" runs whether or not there was an error

    # DELETE returns the number of rows it removed, hence fetchone()[0] above.
    logger.info("Loaded %d rows into %s (mode=%s, replaced %d existing rows).", df.height, TABLE, mode, deleted)
    return df.height


def export_parquet(con: duckdb.DuckDBPyConnection, directory: Path) -> None:
    """Optional: write the table as Parquet files, one folder per snapshot_date.

    Produces e.g. data/parquet/snapshot_date=2026-10-31/data_0.parquet
    ("Hive-style" partitioning). Many tools (Polars, Spark, BigQuery...) read
    such folders directly and skip the dates a query does not need.
    """
    # The path comes from our own code, not from user input, so the f-string is safe here.
    con.execute(
        f"COPY {TABLE} TO '{directory.as_posix()}' "
        "(FORMAT parquet, PARTITION_BY (snapshot_date), OVERWRITE_OR_IGNORE)"
    )
    logger.info("Exported %s to %s", TABLE, directory)


if __name__ == "__main__":
    # Try the load step without calling GitHub: transform the newest raw file and load it.
    #   python -m src.load      (run it twice: today's row count stays the same)
    # transform is imported here, not at the top: only this demo needs it, so
    # load.py itself stays independent of the transform step.
    from src.transform import transform

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()

    raw_files = sorted((PROJECT_ROOT / "data" / "raw").glob("*.json"))
    if not raw_files:
        raise SystemExit("No raw data in data/raw/: run `python -m src.extract` first.")
    raw = json.loads(raw_files[-1].read_text(encoding="utf-8"))
    df = transform(raw, datetime.now(timezone.utc), settings.active_max_days_since_push)

    load(df, settings.db_path, settings.load_mode)

    with connect(settings.db_path, read_only=True) as con:
        # .pl() returns the query result as a Polars DataFrame.
        print(con.sql(f"SELECT snapshot_date, count(*) AS repos FROM {TABLE} GROUP BY 1 ORDER BY 1").pl())