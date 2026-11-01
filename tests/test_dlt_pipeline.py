"""Tests for dlt_pipeline/pipeline.py, fully offline.

- load_with_dlt(): writes to a temporary DuckDB file; dlt's working files go to
  a temporary folder (pipelines_dir), so nothing lands in ~/.dlt.
- extract_with_dlt(): talks to a fake GitHub provided by the `responses` library.

Concepts: docs/concepts/dlt.md, docs/concepts/mocking-http.md
"""

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest
import responses

from dlt_pipeline.pipeline import DATASET, TABLE, extract_with_dlt, load_with_dlt
from src.config import Settings
from src.extract import API_URL
from src.transform import transform

MAX_DAYS = 365
DAY_1 = date(2026, 10, 31)
DAY_2 = date(2026, 11, 1)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.duckdb"


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """Folder for dlt's working files and state during the test."""
    return tmp_path / "dlt"


@pytest.fixture
def day1_df(sample_repos, as_of):
    return transform(sample_repos, as_of, MAX_DAYS)  # repos A and B, 2026-10-31


@pytest.fixture
def day2_df(sample_repos, as_of):
    return transform(sample_repos, as_of + timedelta(days=1), MAX_DAYS)  # 2026-11-01


def rows_per_day(db_path: Path) -> dict[date, int]:
    """Count rows per snapshot_date in the dlt table (schema "github")."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        return dict(
            con.execute(f"SELECT snapshot_date, count(*) FROM {DATASET}.{TABLE} GROUP BY 1 ORDER BY 1").fetchall()
        )


def make_settings(repos=(), orgs=(), token=None) -> Settings:
    """Build Settings directly (same helper as in test_extract.py)."""
    return Settings(
        repos=tuple(repos),
        orgs=tuple(orgs),
        users=(),
        per_page=100,
        active_max_days_since_push=MAX_DAYS,
        db_path=Path("unused.duckdb"),
        load_mode="append",
        github_token=token,
    )


# ---------- load_with_dlt ----------


def test_first_load_writes_rows(db_path, work_dir, day1_df):
    assert load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir) == 2
    assert rows_per_day(db_path) == {DAY_1: 2}


def test_same_day_rerun_is_idempotent(db_path, work_dir, day1_df):
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)

    assert rows_per_day(db_path) == {DAY_1: 2}  # merge on (id, snapshot_date): still 2


def test_append_keeps_previous_days(db_path, work_dir, day1_df, day2_df):
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)
    load_with_dlt(day2_df, db_path, "append", pipelines_dir=work_dir)

    assert rows_per_day(db_path) == {DAY_1: 2, DAY_2: 2}


def test_overwrite_replaces_the_table(db_path, work_dir, day1_df, day2_df):
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)
    load_with_dlt(day2_df, db_path, "overwrite", pipelines_dir=work_dir)

    assert rows_per_day(db_path) == {DAY_2: 2}


def test_empty_dataframe_is_not_loaded(db_path, work_dir, day1_df, as_of):
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)

    assert load_with_dlt(transform([], as_of, MAX_DAYS), db_path, "overwrite", pipelines_dir=work_dir) == 0
    assert rows_per_day(db_path) == {DAY_1: 2}


def test_every_run_is_recorded_in_dlt_loads(db_path, work_dir, day1_df):
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)
    load_with_dlt(day1_df, db_path, "append", pipelines_dir=work_dir)

    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute(f"SELECT count(*) FROM {DATASET}._dlt_loads").fetchone()[0] == 2


def test_unknown_mode_is_rejected(db_path, work_dir, day1_df):
    with pytest.raises(ValueError, match="mode must be one of"):
        load_with_dlt(day1_df, db_path, "upsert", pipelines_dir=work_dir)


# ---------- extract_with_dlt ----------


@responses.activate
def test_extract_follows_pages_and_removes_duplicates():
    next_url = f"{API_URL}/organizations/99/repos?page=2"
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"id": 1, "full_name": "acme/tool"})
    responses.add(
        responses.GET,
        f"{API_URL}/orgs/acme/repos",
        json=[{"id": 1, "full_name": "acme/tool"}, {"id": 2, "full_name": "acme/other"}],
        headers={"Link": f'<{next_url}>; rel="next"'},
    )
    responses.add(responses.GET, f"{API_URL}/organizations/99/repos", json=[{"id": 3, "full_name": "acme/third"}])

    result = extract_with_dlt(make_settings(repos=["acme/tool"], orgs=["acme"]))

    assert sorted(repo["id"] for repo in result) == [1, 2, 3]


@responses.activate
def test_extract_skips_a_missing_repo(caplog):
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"id": 1, "full_name": "acme/tool"})
    responses.add(responses.GET, f"{API_URL}/repos/acme/typo", json={"message": "Not Found"}, status=404)

    result = extract_with_dlt(make_settings(repos=["acme/tool", "acme/typo"]))

    assert [repo["id"] for repo in result] == [1]
    assert "acme/typo" in caplog.text


@responses.activate
def test_extract_sends_the_token():
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"id": 1, "full_name": "acme/tool"})

    extract_with_dlt(make_settings(repos=["acme/tool"], token="github_pat_test"))

    assert responses.calls[0].request.headers["Authorization"] == "Bearer github_pat_test"