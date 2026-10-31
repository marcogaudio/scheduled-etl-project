"""Load the pipeline settings from config/config.toml and environment variables.

This is the only module that reads configuration. Every other module calls
``load_settings()`` and receives one validated, read-only ``Settings`` object,
so repo names, paths and secrets are never hard-coded anywhere else.

Precedence, highest first:
    1. Environment variables (``GITHUB_ETL_*``, plus ``GITHUB_TOKEN``)
    2. config/config.toml
    3. The ``DEFAULT_*`` constants below

Run ``python -m src.config`` to print the settings the pipeline would use.

Concepts: docs/concepts/toml-tomllib.md, docs/concepts/dataclasses.md,
docs/concepts/environment-variables.md, docs/concepts/pathlib.md
"""

import logging
import os
import tomllib  # Standard library since Python 3.11. Reads TOML (it cannot write it).
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # Package "python-dotenv": reads KEY=value lines from .env

# A logger named after this module ("src.config"). main.py decides where logs go.
# Concept: docs/concepts/logging.md
logger = logging.getLogger(__name__)

# __file__ is this file's path: <project>/src/config.py.
# .resolve() makes it absolute; .parent is src/, .parent.parent is the project root.
# Anchoring paths here makes them work from whatever folder you run the command.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.toml"

# Used when neither an environment variable nor the config file sets a value.
DEFAULT_PER_PAGE = 100  # GitHub's maximum page size
DEFAULT_ACTIVE_MAX_DAYS = 365
DEFAULT_DB_PATH = "data/output.duckdb"
DEFAULT_LOAD_MODE = "append"

VALID_LOAD_MODES = ("append", "overwrite")


@dataclass(frozen=True)
class Settings:
    """Everything the pipeline needs to know, already merged and validated.

    frozen=True makes instances read-only: ``settings.load_mode = "x"`` raises
    ``dataclasses.FrozenInstanceError``, so nothing can change the settings by
    accident halfway through a run. Lists are stored as tuples for the same
    reason: a tuple cannot be modified in place.

    Attributes:
        repos: Single repositories to fetch, as "owner/name".
        orgs: Organisations whose public repositories are all fetched.
        users: Users whose public repositories are all fetched.
        per_page: Page size for paginated GitHub endpoints (1-100).
        active_max_days_since_push: Repos pushed longer ago than this are
            dropped by the transform step.
        db_path: Absolute path of the DuckDB database file.
        load_mode: "append" (keep daily history) or "overwrite".
        github_token: Personal access token, or None. repr=False keeps it
            out of print() and logs.
    """

    repos: tuple[str, ...]
    orgs: tuple[str, ...]
    users: tuple[str, ...]
    per_page: int
    active_max_days_since_push: int
    db_path: Path
    load_mode: str
    github_token: str | None = field(default=None, repr=False)

    @property
    def has_token(self) -> bool:
        """True if a GitHub token was found, without revealing it."""
        return self.github_token is not None


def load_settings(config_path: str | Path = DEFAULT_CONFIG_PATH) -> Settings:
    """Build the pipeline settings from defaults, config.toml and environment variables.

    Args:
        config_path: TOML file to read. Defaults to config/config.toml.

    Returns:
        A validated, read-only Settings object.

    Raises:
        FileNotFoundError: If the config file does not exist.
        tomllib.TOMLDecodeError: If the config file is not valid TOML.
        ValueError: If a setting is missing or invalid.
    """
    # Copy KEY=value lines from .env into os.environ. Variables that are
    # already set are NOT overwritten, so a real environment variable (such as
    # the secret GitHub Actions provides) always beats the .env file.
    # If .env does not exist, this silently does nothing.
    load_dotenv(PROJECT_ROOT / ".env")

    # tomllib requires the file to be opened in binary mode ("rb").
    # The result is a nested dict: {"github": {"repos": [...], ...}, "load": {...}}
    with Path(config_path).open("rb") as f:
        config = tomllib.load(f)

    # .get(name, {}) returns an empty dict when a whole [section] is missing,
    # so every lookup below can still fall back to its default.
    github = config.get("github", {})
    transform = config.get("transform", {})
    load = config.get("load", {})

    settings = Settings(
        repos=tuple(_pick(_env_list("GITHUB_ETL_REPOS"), github.get("repos"), ())),
        orgs=tuple(_pick(_env_list("GITHUB_ETL_ORGS"), github.get("orgs"), ())),
        users=tuple(_pick(_env_list("GITHUB_ETL_USERS"), github.get("users"), ())),
        per_page=_pick(_env_int("GITHUB_ETL_PER_PAGE"), github.get("per_page"), DEFAULT_PER_PAGE),
        active_max_days_since_push=_pick(
            _env_int("GITHUB_ETL_ACTIVE_MAX_DAYS"),
            transform.get("active_max_days_since_push"),
            DEFAULT_ACTIVE_MAX_DAYS,
        ),
        db_path=_resolve_path(
            _pick(_env_str("GITHUB_ETL_DB_PATH"), load.get("db_path"), DEFAULT_DB_PATH)
        ),
        load_mode=_pick(_env_str("GITHUB_ETL_LOAD_MODE"), load.get("mode"), DEFAULT_LOAD_MODE),
        # The token is a secret: only ever read from the environment, never from config.toml.
        github_token=_env_str("GITHUB_TOKEN"),
    )

    _validate(settings)
    if not settings.has_token:
        logger.warning("GITHUB_TOKEN is not set: GitHub allows only 60 requests per hour without a token.")
    return settings


def _pick(env_value: Any, file_value: Any, default: Any) -> Any:
    """Return the first value that is not None: env var, then config file, then default.

    This small function *is* the whole precedence rule.
    """
    if env_value is not None:
        return env_value
    if file_value is not None:
        return file_value
    return default


def _env_str(name: str) -> str | None:
    """Read an environment variable as text; None if it is unset or empty.

    Treating "" as unset matters in GitHub Actions, where a variable that is
    not configured often arrives as an empty string.
    """
    value = os.environ.get(name, "").strip()
    return value or None


def _env_list(name: str) -> tuple[str, ...] | None:
    """Read a comma-separated environment variable: "a/b, c/d" -> ("a/b", "c/d").

    Environment variables are always plain text, so lists are written as
    comma-separated values. Returns None if the variable is unset or empty.
    """
    value = _env_str(name)
    if value is None:
        return None
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_int(name: str) -> int | None:
    """Read an environment variable as a whole number; None if it is unset or empty.

    Raises:
        ValueError: If the variable is set but is not a whole number.
    """
    value = _env_str(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        # "from None" hides the less helpful original error from the traceback.
        raise ValueError(f"Environment variable {name} must be a whole number, got {value!r}.") from None


def _resolve_path(value: str | Path) -> Path:
    """Make a path absolute. Relative paths start from the project root.

    "data/output.duckdb" therefore means the same file whether you run the
    pipeline from the project root, from tests/, or in GitHub Actions.
    """
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _validate(settings: Settings) -> None:
    """Stop early with a clear message if a setting is invalid ("fail fast").

    A typo caught here costs a second; the same typo discovered after
    minutes of API calls is much harder to understand.

    Raises:
        ValueError: Describing the first problem found.
    """
    if not (settings.repos or settings.orgs or settings.users):
        raise ValueError("Nothing to fetch: set github.repos, github.orgs or github.users in config.toml.")
    for full_name in settings.repos:
        parts = full_name.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"Repository {full_name!r} must be written as 'owner/name'.")
    if not 1 <= settings.per_page <= 100:
        raise ValueError(f"github.per_page must be between 1 and 100, got {settings.per_page}.")
    if settings.active_max_days_since_push <= 0:
        raise ValueError("transform.active_max_days_since_push must be greater than 0.")
    if settings.load_mode not in VALID_LOAD_MODES:
        raise ValueError(f"load.mode must be one of {VALID_LOAD_MODES}, got {settings.load_mode!r}.")


if __name__ == "__main__":
    # Runs only with "python -m src.config", not when another module imports this file.
    # Concept: docs/concepts/entry-points.md
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    print(settings)  # the token is hidden thanks to repr=False
    print("GitHub token loaded:", settings.has_token)