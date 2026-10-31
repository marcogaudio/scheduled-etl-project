"""Unit tests for src/transform.py.

Run with:  pytest -v
Each test builds a tiny input, runs one function and compares the result
with values worked out by hand (Arrange - Act - Assert).

Concepts: docs/concepts/pytest.md, docs/concepts/pytest-fixtures.md
"""

import copy
from datetime import date, datetime, timezone

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from src.transform import (
    NO_LICENSE,
    OUTPUT_COLUMNS,
    RAW_SCHEMA,
    UNKNOWN_LANGUAGE,
    add_derived,
    clean,
    filter_active,
    to_frame,
    transform,
)

MAX_DAYS = 365


def _derived(repos: list[dict], as_of: datetime) -> pl.DataFrame:
    """Run the first three steps (to_frame -> clean -> add_derived), unfiltered."""
    return add_derived(clean(to_frame(repos)), as_of)


# ---------- to_frame ----------


def test_to_frame_flattens_nested_fields(make_repo):
    df = to_frame([make_repo()])

    assert df["owner_login"].to_list() == ["owner"]
    assert df["license_spdx"].to_list() == ["MIT"]


def test_to_frame_has_exact_columns_and_types(make_repo):
    df = to_frame([make_repo()])

    assert df.columns == list(RAW_SCHEMA)
    assert df.dtypes == list(RAW_SCHEMA.values())


def test_to_frame_empty_input_keeps_all_columns():
    df = to_frame([])

    assert df.height == 0
    assert df.columns == list(RAW_SCHEMA)


# ---------- clean ----------


def test_clean_parses_timestamps_as_utc(make_repo):
    df = clean(to_frame([make_repo()]))

    assert df.schema["pushed_at"] == pl.Datetime("us", "UTC")
    # Two time-zone-aware datetimes are equal when they are the same instant.
    assert df["pushed_at"].to_list() == [datetime(2026, 10, 30, 18, 55, 1, tzinfo=timezone.utc)]


def test_clean_fills_missing_labels(make_repo):
    df = clean(to_frame([make_repo(license=None, language=None)]))

    assert df["license_spdx"].to_list() == [NO_LICENSE]
    assert df["language"].to_list() == [UNKNOWN_LANGUAGE]


# ---------- add_derived ----------


def test_add_derived_matches_worked_example(sample_repos, as_of):
    df = _derived(sample_repos, as_of)

    expected = pl.DataFrame(
        {
            "full_name": ["owner/repo-a", "owner/repo-b", "owner/repo-c", "owner/repo-d"],
            "days_since_last_push": [0, 60, 1020, 0],
            "star_fork_ratio": [12.5, None, 30.0, 12.5],
        }
    )
    assert_frame_equal(df.select("full_name", "days_since_last_push", "star_fork_ratio"), expected)


def test_repo_age_days_matches_python_datetime(make_repo, as_of):
    df = _derived([make_repo()], as_of)

    created = datetime(2020, 5, 13, 8, 0, tzinfo=timezone.utc)
    # Cross-check Polars against Python's own date arithmetic.
    assert df["repo_age_days"].item() == (as_of - created).days


def test_snapshot_date_is_the_run_date(make_repo, as_of):
    df = _derived([make_repo()], as_of)

    assert df["snapshot_date"].to_list() == [date(2026, 10, 31)]


@pytest.mark.parametrize(
    ("stars", "forks", "expected"),
    [
        (100, 10, 10.0),
        (5, 0, None),  # no forks -> null, not infinity
        (0, 7, 0.0),
    ],
)
def test_star_fork_ratio(make_repo, as_of, stars, forks, expected):
    df = _derived([make_repo(stargazers_count=stars, forks_count=forks)], as_of)

    assert df["star_fork_ratio"].item() == expected


# ---------- filter_active ----------


@pytest.mark.parametrize(
    ("overrides", "kept"),
    [
        ({}, True),  # pushed yesterday -> active
        ({"archived": True}, False),
        ({"disabled": True}, False),
        ({"pushed_at": "2024-01-15T00:00:00Z"}, False),  # 1020 days ago
        ({"pushed_at": "2025-10-31T12:00:00Z"}, True),  # exactly 365 days: limit is inclusive
        ({"pushed_at": "2025-10-30T12:00:00Z"}, False),  # 366 days
        ({"pushed_at": None}, False),  # never pushed -> null -> dropped
    ],
)
def test_filter_active(make_repo, as_of, overrides, kept):
    df = filter_active(_derived([make_repo(**overrides)], as_of), MAX_DAYS)

    assert (df.height == 1) is kept


# ---------- transform (all steps together) ----------


def test_transform_keeps_only_active_repos_in_output_order(sample_repos, as_of):
    df = transform(sample_repos, as_of, MAX_DAYS)

    assert df.columns == OUTPUT_COLUMNS
    assert df["full_name"].to_list() == ["owner/repo-a", "owner/repo-b"]


def test_transform_handles_empty_input(as_of):
    df = transform([], as_of, MAX_DAYS)

    assert df.height == 0
    assert df.columns == OUTPUT_COLUMNS


def test_transform_rejects_naive_as_of(sample_repos):
    naive = datetime(2026, 10, 31, 12, 0)  # no tzinfo

    # pytest.raises: the test passes only if this exact error is raised inside the block.
    with pytest.raises(ValueError, match="timezone-aware"):
        transform(sample_repos, naive, MAX_DAYS)


def test_transform_does_not_modify_its_input(sample_repos, as_of):
    before = copy.deepcopy(sample_repos)  # a full, independent copy

    transform(sample_repos, as_of, MAX_DAYS)

    assert sample_repos == before