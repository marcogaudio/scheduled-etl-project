"""Unit tests for src/extract.py, without calling the real GitHub API.

The `responses` library intercepts every request made with `requests` and
answers with the fake responses registered in the test. A request to a URL
that was not registered raises an error, so nothing reaches the internet.

Concept: docs/concepts/mocking-http.md
"""

from pathlib import Path

import pytest
import requests
import responses

from src import extract
from src.config import Settings
from src.extract import API_URL, RateLimitError, fetch_repos


def make_settings(repos=(), orgs=(), users=(), token=None) -> Settings:
    """Build a Settings object directly (no config file needed)."""
    return Settings(
        repos=tuple(repos),
        orgs=tuple(orgs),
        users=tuple(users),
        per_page=100,
        active_max_days_since_push=365,
        db_path=Path("unused.duckdb"),  # extract never uses it
        load_mode="append",
        github_token=token,
    )


@responses.activate  # turn on interception for this test only
def test_token_is_sent_as_bearer_header():
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"id": 1})

    fetch_repos(make_settings(repos=["acme/tool"], token="github_pat_test"))

    assert responses.calls[0].request.headers["Authorization"] == "Bearer github_pat_test"


@responses.activate
def test_duplicates_are_removed_by_id():
    repo = {"id": 1, "full_name": "acme/tool"}
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json=repo)
    responses.add(responses.GET, f"{API_URL}/orgs/acme/repos", json=[repo, {"id": 2, "full_name": "acme/other"}])

    result = fetch_repos(make_settings(repos=["acme/tool"], orgs=["acme"]))

    assert sorted(r["id"] for r in result) == [1, 2]


@responses.activate
def test_pagination_follows_the_link_header():
    # Like real GitHub, the "next" link uses a different URL (/organizations/<id>/...).
    next_url = f"{API_URL}/organizations/99/repos?page=2"
    responses.add(
        responses.GET,
        f"{API_URL}/orgs/acme/repos",
        json=[{"id": 1}, {"id": 2}],
        headers={"Link": f'<{next_url}>; rel="next"'},
    )
    responses.add(responses.GET, f"{API_URL}/organizations/99/repos", json=[{"id": 3}])  # last page: no Link

    result = fetch_repos(make_settings(orgs=["acme"]))

    assert [r["id"] for r in result] == [1, 2, 3]
    assert len(responses.calls) == 2  # exactly two pages requested


@responses.activate
def test_missing_repo_is_skipped_with_a_warning(caplog):
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"id": 1, "full_name": "acme/tool"})
    responses.add(responses.GET, f"{API_URL}/repos/acme/typo", json={"message": "Not Found"}, status=404)

    result = fetch_repos(make_settings(repos=["acme/tool", "acme/typo"]))

    assert [r["id"] for r in result] == [1]
    assert "acme/typo" in caplog.text


@responses.activate
def test_other_http_errors_stop_the_run():
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"message": "Bad credentials"}, status=401)

    with pytest.raises(requests.HTTPError):
        fetch_repos(make_settings(repos=["acme/tool"], token="wrong"))


@responses.activate
def test_rate_limit_waits_until_reset_then_retries(monkeypatch):
    sleeps = []
    # Replace time.sleep with "remember the number": the test runs instantly.
    monkeypatch.setattr(extract.time, "sleep", sleeps.append)

    url = f"{API_URL}/repos/acme/tool"
    reset_at = int(extract.time.time()) + 30  # quota resets in 30 seconds
    # Same URL registered twice: responses returns them in order (403 first, then 200).
    responses.add(
        responses.GET,
        url,
        status=403,
        json={"message": "API rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_at)},
    )
    responses.add(responses.GET, url, json={"id": 1, "full_name": "acme/tool"})

    result = fetch_repos(make_settings(repos=["acme/tool"]))

    assert [r["id"] for r in result] == [1]
    assert len(sleeps) == 1
    assert 29 <= sleeps[0] <= 31  # about 30 s until reset, plus the 1 s margin


@responses.activate
def test_rate_limit_that_is_too_long_raises(monkeypatch):
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", status=429, headers={"Retry-After": "3600"})

    with pytest.raises(RateLimitError):
        fetch_repos(make_settings(repos=["acme/tool"]))