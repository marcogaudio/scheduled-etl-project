"""Extract step: download repository metadata from the GitHub REST API.

Input:  a Settings object (which repos / orgs / users to fetch, and the token).
Output: a list of dicts, one per repository, exactly as GitHub returned them.

This module only talks to GitHub. It does not clean or reshape the data
(that is transform.py) and it does not write to the database (load.py).

Concepts: docs/concepts/http-rest.md, docs/concepts/requests-session.md,
docs/concepts/pagination.md, docs/concepts/rate-limiting.md,
docs/concepts/generators.md
"""

import json
import logging
import time
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from src.config import PROJECT_ROOT, Settings, load_settings

logger = logging.getLogger(__name__)

API_URL = "https://api.github.com"

# Sent with every request (see the plan, section 2.4).
DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",  # pin the API version, like pinning a library
    "User-Agent": "github-etl-learning-project",  # GitHub requires a User-Agent
}

# (seconds to establish the connection, seconds to wait for the answer).
# requests has NO default timeout: without this a stuck request hangs forever.
REQUEST_TIMEOUT = (10, 30)

MAX_RATE_LIMIT_RETRIES = 3
MAX_WAIT_SECONDS = 15 * 60  # never sleep longer than this; fail instead

DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# A type alias: a readable name for "one repository as GitHub returns it".
RawRepo = dict[str, Any]


class RateLimitError(RuntimeError):
    """GitHub's rate limit would make us wait too long, or keeps being hit."""


def make_session(token: str | None) -> requests.Session:
    """Create an HTTP session with GitHub headers, authentication and automatic retries.

    A Session reuses the same network connection for many requests (faster)
    and sends the same headers every time, so they are set up only once.

    Args:
        token: GitHub personal access token, or None for unauthenticated access.

    Returns:
        A configured requests.Session. Use it in a ``with`` block so its
        connections are closed at the end.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if token:
        # "Bearer <token>": the standard way to send an API token.
        session.headers["Authorization"] = f"Bearer {token}"

    # Retry temporary server errors automatically, waiting about 1s, 2s, 4s
    # between attempts (exponential backoff) so GitHub has time to recover.
    # raise_on_status=False: after the last attempt, give the error response
    # back to us, so raise_for_status() in _get() reports it clearly.
    # Rate-limit answers (403/429) are NOT in the list: _get() handles them.
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    # "Mount" the retry policy on every https:// URL this session calls.
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_repos(settings: Settings) -> list[RawRepo]:
    """Fetch every repository the settings ask for, without duplicates.

    Single repos that answer 404 (typo, deleted or private) are skipped with a
    warning, so one bad config entry does not stop the daily run. Any other
    error (bad token, network down, ...) is raised: failing loudly is better
    than silently loading incomplete data.

    Args:
        settings: Which repos / orgs / users to fetch, plus the token.

    Returns:
        One dict per repository, de-duplicated by GitHub's numeric "id".
    """
    # Keyed by repo id, so a repo found twice (e.g. in `repos` and through its
    # org in `orgs`) is stored once. The id never changes, even after a rename.
    repos_by_id: dict[int, RawRepo] = {}

    with make_session(settings.github_token) as session:
        for full_name in settings.repos:
            try:
                repo = get_repo(session, full_name)
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code == 404:
                    logger.warning("Repository %s not found (typo, deleted or private?): skipped.", full_name)
                    continue  # go on with the next repo
                raise  # any other HTTP error: re-raise it unchanged
            repos_by_id[repo["id"]] = repo

        for org in settings.orgs:
            for repo in list_org_repos(session, org, settings.per_page):
                repos_by_id[repo["id"]] = repo

        for user in settings.users:
            for repo in list_user_repos(session, user, settings.per_page):
                repos_by_id[repo["id"]] = repo

    logger.info("Extracted %d unique repositories.", len(repos_by_id))
    return list(repos_by_id.values())


def get_repo(session: requests.Session, full_name: str) -> RawRepo:
    """Fetch one repository: GET /repos/{owner}/{name}.

    Args:
        session: Session from make_session().
        full_name: "owner/name", e.g. "pola-rs/polars".

    Returns:
        The repository as a dict.
    """
    return _get(session, f"{API_URL}/repos/{full_name}").json()


def list_org_repos(session: requests.Session, org: str, per_page: int) -> Iterator[RawRepo]:
    """Yield every public repository of an organisation: GET /orgs/{org}/repos."""
    return paginate(session, f"{API_URL}/orgs/{org}/repos", {"type": "public", "per_page": per_page})


def list_user_repos(session: requests.Session, user: str, per_page: int) -> Iterator[RawRepo]:
    """Yield every repository owned by a user: GET /users/{user}/repos."""
    return paginate(session, f"{API_URL}/users/{user}/repos", {"type": "owner", "per_page": per_page})


def paginate(session: requests.Session, url: str, params: dict[str, Any] | None = None) -> Iterator[RawRepo]:
    """Yield every item of a paginated list endpoint, page after page.

    GitHub returns at most ``per_page`` items per response. When there are
    more, the "Link" response header points to the next page, and requests
    parses it into ``response.links["next"]["url"]``. We keep following
    "next" until it is missing, which means we are on the last page.

    This is a generator (it uses ``yield``): it hands out one item at a time
    and only downloads the next page when the caller asks for more.

    Args:
        session: Session from make_session().
        url: URL of the first page.
        params: Query parameters for the first page, e.g. {"per_page": 100}.

    Yields:
        One item (here: one repository dict) at a time.
    """
    next_url: str | None = url
    page = 0
    while next_url:
        response = _get(session, next_url, params=params)
        page += 1
        items = response.json()  # a list of repo dicts
        logger.debug("Page %d: %d items from %s", page, len(items), next_url)
        yield from items
        # .get(..., {}) avoids a KeyError on the last page, which has no "next" link.
        next_url = response.links.get("next", {}).get("url")
        # The "next" URL already contains per_page/page in its query string,
        # so the parameters must not be sent a second time.
        params = None


def _get(session: requests.Session, url: str, params: dict[str, Any] | None = None) -> requests.Response:
    """Send one GET request; wait and retry if GitHub's rate limit is hit.

    Args:
        session: Session from make_session().
        url: Full URL to request.
        params: Optional query-string parameters.

    Returns:
        The successful (2xx) response.

    Raises:
        RateLimitError: If the wait would exceed MAX_WAIT_SECONDS, or the limit
            is still hit after MAX_RATE_LIMIT_RETRIES attempts.
        requests.HTTPError: For other error statuses (401 bad token, 404 ...).
        requests.RequestException: For network problems (no connection, timeout ...).
    """
    for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 1):
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)

        if not _is_rate_limited(response):
            # Raises requests.HTTPError for 4xx/5xx; does nothing for 2xx.
            response.raise_for_status()
            _log_quota(response)
            return response

        wait = _seconds_to_wait(response)
        if wait > MAX_WAIT_SECONDS:
            raise RateLimitError(
                f"GitHub rate limit hit; waiting would take {wait:.0f}s "
                f"(more than the {MAX_WAIT_SECONDS}s limit). Set GITHUB_TOKEN or try later."
            )
        logger.warning(
            "Rate limited by GitHub (attempt %d/%d): sleeping %.0fs.", attempt, MAX_RATE_LIMIT_RETRIES, wait
        )
        time.sleep(wait)

    raise RateLimitError(f"Still rate limited after {MAX_RATE_LIMIT_RETRIES} attempts: {url}")


def _is_rate_limited(response: requests.Response) -> bool:
    """True if GitHub refused the request because of a rate limit.

    GitHub answers 429, or 403 together with one of: "X-RateLimit-Remaining: 0",
    a "Retry-After" header, or "rate limit" in the message. A 403 with none of
    these is a real permission error and must not be retried.
    (response.headers is case-insensitive: "retry-after" works too.)
    """
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    return (
        response.headers.get("X-RateLimit-Remaining") == "0"
        or "Retry-After" in response.headers
        or "rate limit" in response.text.lower()
    )


def _seconds_to_wait(response: requests.Response) -> float:
    """How long to sleep before retrying, following GitHub's documented rules.

    1. A "Retry-After: <seconds>" header -> wait exactly that long.
    2. Quota used up -> wait until "X-RateLimit-Reset" (a Unix timestamp).
    3. Otherwise (secondary limit without hints) -> wait 60 seconds.
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        return float(retry_after)
    if response.headers.get("X-RateLimit-Remaining") == "0":
        reset_at = int(response.headers["X-RateLimit-Reset"])  # seconds since 1970-01-01 UTC
        # max(..., 0) avoids a negative wait if the reset time has just passed;
        # +1 is a safety margin for small clock differences.
        return max(reset_at - time.time(), 0) + 1
    return 60.0


def _log_quota(response: requests.Response) -> None:
    """Log how many API requests are left this hour; warn when it is low."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    limit = response.headers.get("X-RateLimit-Limit")
    if remaining is None:
        return
    logger.debug("GitHub quota: %s of %s requests left.", remaining, limit)
    if int(remaining) < 10:
        logger.warning("Only %s GitHub API requests left this hour.", remaining)


def save_raw(repos: list[RawRepo], snapshot_date: date, directory: Path = DEFAULT_RAW_DIR) -> Path:
    """Save the untouched API data to <directory>/<YYYY-MM-DD>.json.

    The raw copy lets you debug the transform step without calling the API
    again, and gives you real examples to copy into test fixtures.

    Args:
        repos: Output of fetch_repos().
        snapshot_date: Date of this run; used as the file name.
        directory: Where to write. Defaults to data/raw/ (gitignored).

    Returns:
        The path of the written file.
    """
    directory.mkdir(parents=True, exist_ok=True)  # create data/raw/ if missing
    path = directory / f"{snapshot_date.isoformat()}.json"  # e.g. 2026-10-31.json
    # indent=2: human-readable. ensure_ascii=False: keep non-English characters as they are.
    path.write_text(json.dumps(repos, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved raw data to %s", path)
    return path


if __name__ == "__main__":
    # Try the extract step on its own: python -m src.extract
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    repos = fetch_repos(load_settings())
    for repo in repos:
        # :<30 pads to 30 characters (left-aligned), :>7 right-aligns in 7: a neat table.
        print(f"{repo['full_name']:<30} stars={repo['stargazers_count']:>7}  pushed_at={repo['pushed_at']}")
    save_raw(repos, datetime.now(timezone.utc).date())