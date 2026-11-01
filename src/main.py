"""Entry point of the ETL pipeline: extract -> transform -> load, in one command.

Usage (from the project root):
    python -m src.main                      # normal daily run
    python -m src.main --dry-run            # extract + transform, don't write to the database
    python -m src.main --mode overwrite     # replace the whole table this time
    python -m src.main --log-level DEBUG    # show every API page and the remaining quota
    python -m src.main --help               # list all options

This module contains no ETL logic of its own. It reads the settings, calls the
three steps in order, measures and logs them, and turns success or failure into
an exit code (0 = OK, 1 = failed) that GitHub Actions understands.

Concepts: docs/concepts/entry-points.md, docs/concepts/argparse.md,
docs/concepts/logging.md, docs/concepts/exit-codes.md
"""

import argparse
import dataclasses
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config import DEFAULT_CONFIG_PATH, VALID_LOAD_MODES, Settings, load_settings
from src.extract import fetch_repos, save_raw
from src.load import load
from src.transform import transform
from dlt_pipeline.pipeline import extract_with_dlt, load_with_dlt

ENGINES = ["manual", "dlt"]

logger = logging.getLogger(__name__)

# How every log line looks: time, level (padded to 8 characters), module name, message.
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


@dataclass(frozen=True)
class RunSummary:
    """What one run did: logged at the end and checked by the tests."""

    as_of: datetime
    extracted: int  # repositories downloaded from GitHub
    active: int  # rows left after the transform's "active" filter
    loaded: int  # rows written to DuckDB (0 for a dry run)
    seconds: float  # total duration of the run


def main(argv: list[str] | None = None) -> int:
    """Run the whole pipeline from the command line.

    Args:
        argv: Command-line arguments without the program name. None means
            "use the real command line" (sys.argv); tests pass their own list.

    Returns:
        The exit code: 0 if the run succeeded, 1 if it failed.
    """
    args = parse_args(argv)  # an invalid option makes argparse exit with code 2
    configure_logging(args.log_level)

    try:
        settings = apply_cli_overrides(load_settings(args.config), args)
        # ONE timestamp for the whole run: every step measures from the same "now".
        as_of = datetime.now(timezone.utc)
        summary = run(settings, as_of, dry_run=args.dry_run, engine=args.engine)
    except Exception:
        # The only place that catches every error: log it with its full
        # traceback, then report failure through the exit code.
        logger.exception("ETL run failed.")
        return 1

    logger.info(
        "Run finished in %.1fs: %d repos extracted, %d active, %d loaded into %s (mode=%s%s).",
        summary.seconds,
        summary.extracted,
        summary.active,
        summary.loaded,
        settings.db_path,
        settings.load_mode,
        ", dry run" if args.dry_run else "",
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define and read the command-line options.

    argparse also generates --help automatically and rejects invalid values
    (e.g. --mode upsert) with a usage message and exit code 2.

    Args:
        argv: Arguments to parse; None means sys.argv[1:].

    Returns:
        A Namespace with one attribute per option: args.config, args.mode,
        args.dry_run, args.log_level (dashes become underscores).
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Scheduled GitHub ETL: GitHub API -> Polars -> DuckDB.",
    )
    parser.add_argument(
        "--config",
        type=Path,  # convert the typed text into a pathlib.Path
        default=DEFAULT_CONFIG_PATH,
        help="TOML configuration file (default: config/config.toml).",
    )
    parser.add_argument(
        "--mode",
        choices=VALID_LOAD_MODES,  # anything else is rejected
        default=None,  # None = "not given": keep the value from the config
        help="Override load.mode for this run only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",  # a flag without a value: present = True
        help="Extract and transform, but do not write to the database.",
    )
    parser.add_argument(
        "--engine",
        choices=ENGINES,
        default="manual",
        help="manual = hand-written extract/load (Phases 2 and 5); dlt = dlt version (Phase 7).",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    """Show log messages from every module on the console, with time and level.

    Each module has its own logger (logging.getLogger(__name__)); they all pass
    their messages up to the root logger configured here. Only the entry point
    configures logging; the other modules just use it.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    # urllib3 (used by requests) logs every connection at DEBUG level: keep it quieter.
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def apply_cli_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """Apply command-line options on top of the settings.

    Precedence: command line > environment variable > config file > default.
    Settings is frozen, so instead of changing it we build a modified copy
    with dataclasses.replace().
    """
    if args.mode is not None:
        settings = dataclasses.replace(settings, load_mode=args.mode)
    return settings


def run(settings: Settings, as_of: datetime, dry_run: bool = False, engine: str = "manual") -> RunSummary:
    """Execute extract -> transform -> load once, with the chosen engine.

    Args:
        settings: Validated settings.
        as_of: Timestamp of this run (UTC), passed to every step.
        dry_run: If True, skip the load step: nothing is written to DuckDB.
        engine: "manual" (Phases 2 + 5) or "dlt" (Phase 7). The transform is shared.

    Returns:
        A RunSummary with the row counts and the duration.

    Raises:
        RuntimeError: If no repository at all could be extracted.
        Any error raised by the steps themselves (network, database, ...).
    """
    start = time.perf_counter()

    with timed(f"extract ({engine})"):
        raw = extract_with_dlt(settings) if engine == "dlt" else fetch_repos(settings)
        save_raw(raw, as_of.date())
    if not raw:
        raise RuntimeError("No repositories were extracted: check github.repos / orgs / users in the config.")

    with timed("transform"):
        df = transform(raw, as_of, settings.active_max_days_since_push)  # identical for both engines

    if dry_run:
        logger.info("Dry run: the load step is skipped. First rows:\n%s", df.head(5))
        loaded = 0
    else:
        with timed(f"load ({engine})"):
            if engine == "dlt":
                loaded = load_with_dlt(df, settings.db_path, settings.load_mode)
            else:
                loaded = load(df, settings.db_path, settings.load_mode)

    return RunSummary(
        as_of=as_of,
        extracted=len(raw),
        active=df.height,
        loaded=loaded,
        seconds=time.perf_counter() - start,
    )


@contextmanager
def timed(step: str) -> Iterator[None]:
    """Log when a step starts and how long it took.

    Usage:  with timed("extract"): ...
    @contextmanager turns this generator into a ``with`` block: the code before
    ``yield`` runs when the block starts, the code after it when the block ends.
    If the block raises, the DONE line is skipped and the error continues upward.
    """
    logger.info("START %s", step)
    start = time.perf_counter()  # a clock made for measuring durations
    yield
    logger.info("DONE  %s in %.2fs", step, time.perf_counter() - start)


if __name__ == "__main__":
    # Hand main()'s return value (0 or 1) to the operating system as the exit code.
    sys.exit(main())