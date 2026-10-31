"""Transform step: turn raw GitHub JSON into a clean, typed Polars DataFrame.

Input:  the list of repo dicts from extract.py, the run timestamp (as_of)
        and the "active" threshold in days.
Output: one row per *active* repository, with the columns, types and order
        of OUTPUT_COLUMNS, ready for load.py.

Every function here is *pure*: it only uses its arguments, returns a new
DataFrame and changes nothing else (no API calls, no files, no clock).
That makes the logic easy to test with small hand-written examples.

Concepts: docs/concepts/polars-dataframe.md, docs/concepts/polars-expressions.md,
docs/concepts/polars-dtypes.md, docs/concepts/datetimes-timezones.md,
docs/concepts/pure-functions.md
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import polars as pl

from src.config import PROJECT_ROOT, load_settings

logger = logging.getLogger(__name__)

# Same alias as in extract.py: one repository as GitHub returns it.
RawRepo = dict[str, Any]

# Labels used instead of null, so missing values still form a group in counts.
UNKNOWN_LANGUAGE = "Unknown"
NO_LICENSE = "NONE"

# The fields we keep from the raw JSON, with their exact types.
# Giving Polars the schema (instead of letting it guess from the data) keeps
# the result identical every day, even when a value is null for every repo.
RAW_SCHEMA = {
    "id": pl.Int64,  # GitHub ids are too big for a 32-bit integer
    "full_name": pl.String,
    "owner_login": pl.String,
    "language": pl.String,  # may be null
    "license_spdx": pl.String,  # may be null
    "stargazers_count": pl.Int64,
    "forks_count": pl.Int64,
    "open_issues_count": pl.Int64,
    "topics": pl.List(pl.String),  # each cell holds a list of strings
    "fork": pl.Boolean,
    "archived": pl.Boolean,
    "disabled": pl.Boolean,
    "created_at": pl.String,  # still text here; clean() parses the three timestamps
    "updated_at": pl.String,
    "pushed_at": pl.String,  # may be null for a repo that was never pushed to
}

# Final columns, in the order load.py expects them: the "contract" between
# the transform and load steps.
OUTPUT_COLUMNS = [
    "snapshot_date",
    "id",
    "full_name",
    "owner_login",
    "language",
    "license_spdx",
    "stargazers_count",
    "forks_count",
    "open_issues_count",
    "star_fork_ratio",
    "topics",
    "fork",
    "archived",
    "disabled",
    "created_at",
    "updated_at",
    "pushed_at",
    "repo_age_days",
    "days_since_last_push",
]


def transform(raw: list[RawRepo], as_of: datetime, max_days_since_push: int) -> pl.DataFrame:
    """Run the whole transform: raw JSON -> clean, filtered DataFrame.

    Args:
        raw: Repositories from extract.fetch_repos().
        as_of: Timestamp of this run, timezone-aware (UTC). Every "days since"
            value is measured from it, so the same input always gives the same output.
        max_days_since_push: Repos pushed longer ago than this are dropped.

    Returns:
        One row per active repository, with the columns in OUTPUT_COLUMNS.

    Raises:
        ValueError: If as_of has no time zone.
    """
    if as_of.tzinfo is None:
        # A "naive" datetime (no time zone) cannot be compared with the UTC
        # timestamps from GitHub; refuse it here with a clear message.
        raise ValueError("as_of must be timezone-aware, e.g. datetime.now(timezone.utc).")

    # .pipe(f, x) calls f(df, x), so the steps read top to bottom (like |> in R).
    df = (
        to_frame(raw)
        .pipe(clean)
        .pipe(add_derived, as_of)
        .pipe(filter_active, max_days_since_push)
        .select(OUTPUT_COLUMNS)
    )
    logger.info("Transformed %d raw repositories into %d active ones.", len(raw), df.height)
    return df


def to_frame(raw: list[RawRepo]) -> pl.DataFrame:
    """Keep only the fields we need, flatten nested ones, and build a typed DataFrame.

    GitHub nests some values, e.g. {"owner": {"login": "pola-rs", ...}} and
    {"license": {"spdx_id": "MIT", ...}} (or "license": null). They become
    the flat columns owner_login and license_spdx.

    Args:
        raw: Repositories as GitHub returned them.

    Returns:
        A DataFrame with exactly the RAW_SCHEMA columns and types. An empty
        input gives an empty DataFrame that still has every column.
    """
    # List comprehension: build one flat dict per raw repo.
    rows = [_select_fields(repo) for repo in raw]
    return pl.DataFrame(rows, schema=RAW_SCHEMA)


def _select_fields(repo: RawRepo) -> dict[str, Any]:
    """Pick the RAW_SCHEMA fields from one raw repo dict."""
    # `or {}` turns a null (None) owner/license into an empty dict, so .get() still works.
    # The trailing underscore in license_ avoids hiding Python's built-in name license.
    owner = repo.get("owner") or {}
    license_ = repo.get("license") or {}
    return {
        # Square brackets for required fields: a missing id should fail loudly.
        "id": repo["id"],
        "full_name": repo["full_name"],
        "owner_login": owner.get("login"),
        # .get() for optional fields: returns None if the key is missing.
        "language": repo.get("language"),
        "license_spdx": license_.get("spdx_id"),
        "stargazers_count": repo.get("stargazers_count"),
        "forks_count": repo.get("forks_count"),
        "open_issues_count": repo.get("open_issues_count"),
        "topics": repo.get("topics") or [],
        "fork": repo.get("fork"),
        "archived": repo.get("archived"),
        "disabled": repo.get("disabled"),
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
    }


def clean(df: pl.DataFrame) -> pl.DataFrame:
    """Fix types and replace missing labels.

    - created_at / updated_at / pushed_at: text like "2026-10-30T18:55:01Z"
      -> real UTC datetimes, so they can be subtracted.
    - language null -> "Unknown", license_spdx null -> "NONE", so they still
      form a group in counts instead of disappearing as null.
    - archived / disabled / fork null -> False, so the filter never sees null.

    Args:
        df: Output of to_frame().

    Returns:
        A new DataFrame (the input is not modified).
    """
    # with_columns: an expression whose result has an existing column's name
    # replaces that column; all other columns are kept unchanged.
    return df.with_columns(
        # One expression applied to three columns at once.
        pl.col("created_at", "updated_at", "pushed_at").str.to_datetime(time_zone="UTC"),
        pl.col("language").fill_null(UNKNOWN_LANGUAGE),
        pl.col("license_spdx").fill_null(NO_LICENSE),
        pl.col("archived", "disabled", "fork").fill_null(False),
    )


def add_derived(df: pl.DataFrame, as_of: datetime) -> pl.DataFrame:
    """Add computed columns.

    - days_since_last_push: whole days from the last push to as_of.
    - repo_age_days: whole days from creation to as_of.
    - star_fork_ratio: stars / forks; null when a repo has no forks
      (dividing by zero would give "inf", which is meaningless here).
    - snapshot_date: the date of this run; load.py keeps one snapshot per day.

    Args:
        df: Output of clean().
        as_of: Timestamp of this run (timezone-aware, UTC).

    Returns:
        A new DataFrame with the four extra columns.
    """
    # pl.lit() turns a plain Python value into an expression, so it can be
    # combined with columns. Datetime minus datetime gives a Duration;
    # .dt.total_days() converts it to whole days (rounded down).
    now = pl.lit(as_of)
    return df.with_columns(
        (now - pl.col("pushed_at")).dt.total_days().alias("days_since_last_push"),
        (now - pl.col("created_at")).dt.total_days().alias("repo_age_days"),
        # when / then / otherwise: an if/else evaluated for every row.
        pl.when(pl.col("forks_count") > 0)
        .then(pl.col("stargazers_count") / pl.col("forks_count"))
        .otherwise(None)
        .alias("star_fork_ratio"),
        pl.lit(as_of.date()).alias("snapshot_date"),
    )


def filter_active(df: pl.DataFrame, max_days_since_push: int) -> pl.DataFrame:
    """Keep only active repositories.

    Active = not archived AND not disabled AND pushed within the last
    max_days_since_push days. Repos with no push date (null) are dropped too,
    because filter() keeps only the rows where the condition is True.

    Args:
        df: Output of add_derived() (needs days_since_last_push).
        max_days_since_push: Threshold from the settings.

    Returns:
        A new DataFrame with only the active rows.
    """
    # ~ is NOT, & is AND, | is OR: Python's `not` / `and` / `or` don't work on columns.
    # The comparison needs its own parentheses because & is evaluated before <=.
    return df.filter(
        ~pl.col("archived")
        & ~pl.col("disabled")
        & (pl.col("days_since_last_push") <= max_days_since_push)
    )


if __name__ == "__main__":
    # Try the transform on the raw file saved by the extract step, without calling GitHub:
    #   python -m src.transform
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    raw_files = sorted((PROJECT_ROOT / "data" / "raw").glob("*.json"))
    if not raw_files:
        # SystemExit prints the message and ends the program with exit code 1.
        raise SystemExit("No raw data in data/raw/: run `python -m src.extract` first.")
    latest = raw_files[-1]  # names are dates (YYYY-MM-DD), so sorting puts the newest last
    raw = json.loads(latest.read_text(encoding="utf-8"))

    settings = load_settings()
    df = transform(raw, datetime.now(timezone.utc), settings.active_max_days_since_push)

    # pl.Config temporarily changes how tables are printed; tbl_cols=-1 shows every column.
    with pl.Config(tbl_cols=-1):
        print(df)
    print(df.schema)