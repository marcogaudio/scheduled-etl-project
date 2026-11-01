"""Unit tests for src/load.py.

Every test writes to a fresh DuckDB file inside pytest's temporary folder,
so your real data/output.duckdb is never touched.

Concepts: docs/concepts/idempotency.md, docs/concepts/transactions.md
"""

from datetime import date, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from src.load import LATEST_VIEW, TABLE, load
from src.transform import transform

MAX_DAYS = 365
DAY_1 = date(2026, 10, 31)
DAY_2 = date(2026, 11, 1)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A database file path in a fresh temporary folder (the file doesn't exist yet)."""
    return tmp_path / "test.duckdb"


@pytest.fixture
def day1_df(sample_repos, as_of) -> pl.DataFrame:
    """Transformed sample data for 2026-10-31: the 2 active repos A and B."""
    return transform(sample_repos, as_of, MAX_DAYS)


@pytest.fixture
def day2_df(sample_repos, as_of) -> pl.DataFrame:
    """The same repos one day later (snapshot_date 2026-11-01)."""
    return transform(sample_repos, as_of + timedelta(days=1), MAX_DAYS)


def rows_per_day(db_path: Path) -> dict[date, int]:
    """Count the rows of each snapshot_date, e.g. {date(2026, 10, 31): 2}."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        return dict(con.execute(f"SELECT snapshot_date, count(*) FROM {TABLE} GROUP BY 1 ORDER BY 1").fetchall())


def test_first_load_creates_table_and_writes_rows(db_path, day1_df):
    written = load(day1_df, db_path, "append")

    assert written == 2
    assert rows_per_day(db_path) == {DAY_1: 2}


def test_rerun_on_the_same_day_is_idempotent(db_path, day1_df):
    load(day1_df, db_path, "append")
    load(day1_df, db_path, "append")  # same day again

    assert rows_per_day(db_path) == {DAY_1: 2}  # still 2, not 4


def test_no_duplicate_keys_after_reruns(db_path, day1_df):
    for _ in range(3):
        load(day1_df, db_path, "append")

    with duckdb.connect(str(db_path), read_only=True) as con:
        duplicates = con.execute(
            f"SELECT id, snapshot_date FROM {TABLE} GROUP BY 1, 2 HAVING count(*) > 1"
        ).fetchall()
    assert duplicates == []


def test_append_keeps_previous_days(db_path, day1_df, day2_df):
    load(day1_df, db_path, "append")
    load(day2_df, db_path, "append")

    assert rows_per_day(db_path) == {DAY_1: 2, DAY_2: 2}


def test_latest_view_shows_only_the_newest_day(db_path, day1_df, day2_df):
    load(day1_df, db_path, "append")
    load(day2_df, db_path, "append")

    with duckdb.connect(str(db_path), read_only=True) as con:
        days = con.execute(f"SELECT DISTINCT snapshot_date FROM {LATEST_VIEW}").fetchall()
    assert days == [(DAY_2,)]


def test_overwrite_replaces_the_whole_table(db_path, day1_df, day2_df):
    load(day1_df, db_path, "append")
    load(day2_df, db_path, "overwrite")

    assert rows_per_day(db_path) == {DAY_2: 2}


def test_empty_dataframe_leaves_the_table_unchanged(db_path, day1_df, as_of):
    load(day1_df, db_path, "append")
    empty = transform([], as_of, MAX_DAYS)

    written = load(empty, db_path, "overwrite")  # would wipe everything without the guard

    assert written == 0
    assert rows_per_day(db_path) == {DAY_1: 2}


def test_failed_insert_rolls_back_the_delete(db_path, day1_df):
    load(day1_df, db_path, "append")
    # An extra column the table doesn't have makes the INSERT fail AFTER the DELETE ran.
    broken = day1_df.with_columns(pl.lit(1).alias("not_a_real_column"))

    with pytest.raises(duckdb.Error):
        load(broken, db_path, "append")

    assert rows_per_day(db_path) == {DAY_1: 2}  # the deleted rows came back


def test_values_survive_the_round_trip(db_path, day1_df):
    load(day1_df, db_path, "append")

    columns = ["full_name", "stargazers_count", "star_fork_ratio", "topics"]
    with duckdb.connect(str(db_path), read_only=True) as con:
        stored = con.sql(f"SELECT {', '.join(columns)} FROM {TABLE} ORDER BY id").pl()
    assert_frame_equal(stored, day1_df.sort("id").select(columns))


def test_unknown_mode_is_rejected(db_path, day1_df):
    with pytest.raises(ValueError, match="mode must be one of"):
        load(day1_df, db_path, "upsert")