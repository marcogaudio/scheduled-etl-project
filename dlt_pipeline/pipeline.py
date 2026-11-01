"""dlt version of the extract and load steps.

- extract_with_dlt(): download the repositories with dlt's REST client
  (replaces src/extract.py:fetch_repos).
- load_with_dlt(): write the transformed DataFrame into DuckDB with a dlt
  pipeline (replaces src/load.py:load).

The transform step is NOT duplicated: src/transform.py is used by both engines.
The data lands in the same DuckDB file, in the schema "github".

Run on its own:   python -m dlt_pipeline.pipeline
Or through main:  python -m src.main --engine dlt

Concepts: docs/concepts/dlt.md, docs/concepts/dlt-write-dispositions.md,
docs/concepts/apache-arrow.md
"""

import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dlt
import polars as pl
import pyarrow as pa
import requests  # only for the HTTPError exception class
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator

from src.config import Settings, load_settings
from src.extract import API_URL, DEFAULT_HEADERS  # reuse the same URL and headers as Phase 2
from src.transform import transform

logger = logging.getLogger(__name__)

PIPELINE_NAME = "github_etl"  # names dlt's working folder: ~/.dlt/pipelines/github_etl
DATASET = "github"  # becomes the DuckDB schema that holds the tables
TABLE = "repo_snapshots"

# Our load.mode -> dlt write disposition (see the plan, section 7.5).
WRITE_DISPOSITIONS = {
    "append": "merge",  # keep history; a same-day re-run updates rows by primary key
    "overwrite": "replace",  # replace the whole table
}

RawRepo = dict[str, Any]


# ---------- extract ----------


def make_client(token: str | None) -> RESTClient:
    """Create dlt's REST client for the GitHub API.

    It replaces make_session() and paginate() from Phase 2: dlt adds the base
    URL to every path, sends the headers and token, follows the "Link: next"
    header page by page, and retries temporary errors automatically.
    """
    return RESTClient(
        base_url=API_URL,
        headers=DEFAULT_HEADERS,
        auth=BearerTokenAuth(token) if token else None,  # no token = unauthenticated
        paginator=HeaderLinkPaginator(),  # GitHub puts the next page in the Link header
    )


def extract_with_dlt(settings: Settings) -> list[RawRepo]:
    """Fetch every configured repository with dlt's REST client, without duplicates.

    Same behaviour as extract.fetch_repos(): a single repo answering 404 is
    skipped with a warning; any other error stops the run.

    Args:
        settings: Which repos / orgs / users to fetch, plus the token.

    Returns:
        One dict per repository (raw GitHub JSON), de-duplicated by "id".
    """
    client = make_client(settings.github_token)
    repos_by_id: dict[int, RawRepo] = {}

    for full_name in settings.repos:
        try:
            response = client.get(f"/repos/{full_name}")
            response.raise_for_status()  # make sure error statuses become exceptions
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                logger.warning("Repository %s not found (typo, deleted or private?): skipped.", full_name)
                continue
            raise
        repo = response.json()
        repos_by_id[repo["id"]] = repo

    # Paginated list endpoints: client.paginate() yields one PAGE (a list of repos) at a time.
    list_endpoints = [(f"/orgs/{org}/repos", {"type": "public"}) for org in settings.orgs]
    list_endpoints += [(f"/users/{user}/repos", {"type": "owner"}) for user in settings.users]
    for path, params in list_endpoints:
        for page in client.paginate(path, params={**params, "per_page": settings.per_page}):
            for repo in page:
                repos_by_id[repo["id"]] = repo

    logger.info("dlt extract: %d unique repositories.", len(repos_by_id))
    return list(repos_by_id.values())


# ---------- load ----------


@dlt.resource(name=TABLE, write_disposition="merge", primary_key=("id", "snapshot_date"))
def repo_snapshots(df: pl.DataFrame) -> Iterator[pa.Table]:
    """dlt resource: hands the transformed rows to dlt as one Arrow table.

    The decorator tells dlt the table name, how to combine new rows with
    existing ones (merge) and which columns identify a row (primary key).
    A resource is a generator: it *yields* data; dlt pulls it during pipeline.run().
    """
    yield df.to_arrow()


def make_pipeline(db_path: Path, pipelines_dir: Path | None = None) -> dlt.Pipeline:
    """Create the dlt pipeline that writes into our DuckDB file.

    Args:
        db_path: The DuckDB file (the same one the manual engine uses).
        pipelines_dir: Where dlt keeps its working files and state. None means
            dlt's default (~/.dlt/pipelines); tests pass a temporary folder.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)  # create data/ if missing
    return dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=dlt.destinations.duckdb(str(db_path)),
        dataset_name=DATASET,
        pipelines_dir=str(pipelines_dir) if pipelines_dir else None,
    )


def load_with_dlt(df: pl.DataFrame, db_path: Path, mode: str, pipelines_dir: Path | None = None) -> int:
    """Write one run's DataFrame into DuckDB (schema "github") with dlt.

    Args:
        df: Output of transform.transform().
        db_path: The DuckDB file.
        mode: "append" (dlt merge: keep history) or "overwrite" (dlt replace).
        pipelines_dir: Optional folder for dlt's working files (used by tests).

    Returns:
        The number of rows handed to dlt (0 if df is empty).

    Raises:
        ValueError: If mode is unknown.
        Any dlt error if a load job fails.
    """
    if mode not in WRITE_DISPOSITIONS:
        raise ValueError(f"mode must be one of {tuple(WRITE_DISPOSITIONS)}, got {mode!r}.")
    if df.is_empty():
        # Same protection as load.py: an empty "replace" would wipe the history.
        logger.warning("Nothing to load (0 rows): the dlt table was left unchanged.")
        return 0

    pipeline = make_pipeline(db_path, pipelines_dir)
    # write_disposition passed to run() overrides the decorator's default for this run.
    load_info = pipeline.run(repo_snapshots(df), write_disposition=WRITE_DISPOSITIONS[mode])
    load_info.raise_on_failed_jobs()  # turn any failed load job into an exception

    logger.info(
        "dlt load: %d rows into %s.%s (write_disposition=%s).", df.height, DATASET, TABLE, WRITE_DISPOSITIONS[mode]
    )
    logger.debug("dlt load info:\n%s", load_info)
    return df.height


if __name__ == "__main__":
    # Run the whole dlt version on its own:  python -m dlt_pipeline.pipeline
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    as_of = datetime.now(timezone.utc)

    raw = extract_with_dlt(settings)
    df = transform(raw, as_of, settings.active_max_days_since_push)
    load_with_dlt(df, settings.db_path, settings.load_mode)