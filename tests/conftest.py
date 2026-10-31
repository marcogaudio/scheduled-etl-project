"""Shared test data (fixtures), loaded automatically by pytest.

A function decorated with @pytest.fixture becomes available to every test
that names it as a parameter: pytest calls the fixture and passes the result in.

Concept: docs/concepts/pytest-fixtures.md
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import pytest

# The fixed "now" for all tests, so expected day counts can be worked out by hand.
AS_OF = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _make_raw_repo(**overrides: Any) -> dict[str, Any]:
    """Build one fake GitHub repo dict; keyword arguments replace the defaults.

    Example: _make_raw_repo(id=2, archived=True)
    The defaults describe repo "A" from the plan's worked example (section 3.5).
    """
    repo = {
        "id": 1,
        "full_name": "owner/repo-a",
        "owner": {"login": "owner"},
        "language": "Python",
        "license": {"key": "mit", "spdx_id": "MIT", "name": "MIT License"},
        "stargazers_count": 1500,
        "forks_count": 120,
        "open_issues_count": 42,
        "topics": ["etl", "dataframe"],
        "fork": False,
        "archived": False,
        "disabled": False,
        "created_at": "2020-05-13T08:00:00Z",
        "updated_at": "2026-10-30T19:12:44Z",
        "pushed_at": "2026-10-30T18:55:01Z",
    }
    repo.update(overrides)  # replace only the keys the test passed in
    return repo


@pytest.fixture
def as_of() -> datetime:
    """The run timestamp used by every test: 2026-10-31 12:00 UTC."""
    return AS_OF


@pytest.fixture
def make_repo() -> Callable[..., dict[str, Any]]:
    """Factory fixture: gives tests a function that builds fake repo dicts."""
    return _make_raw_repo


@pytest.fixture
def sample_repos(make_repo: Callable[..., dict[str, Any]]) -> list[dict[str, Any]]:
    """The plan's worked example (repos A, B, C) plus an archived repo D.

    A fixture can use another fixture (here: make_repo) by naming it as a parameter.
    """
    return [
        make_repo(id=1, full_name="owner/repo-a"),  # active, 0 days, ratio 12.5
        make_repo(  # active, 60 days, no forks, no license, no language
            id=2,
            full_name="owner/repo-b",
            stargazers_count=40,
            forks_count=0,
            license=None,
            language=None,
            pushed_at="2026-09-01T00:00:00Z",
        ),
        make_repo(  # stale: last push 1020 days ago
            id=3,
            full_name="owner/repo-c",
            stargazers_count=900,
            forks_count=30,
            pushed_at="2024-01-15T00:00:00Z",
        ),
        make_repo(id=4, full_name="owner/repo-d", archived=True),  # archived
    ]