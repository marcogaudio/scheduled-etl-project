"""Tests for src/main.py: the wiring of the steps, the CLI options and the exit codes.

GitHub is replaced by a fake that returns the sample repos from conftest.py,
so the tests run offline. Every test uses its own temporary config and database.

Concepts: docs/concepts/monkeypatch.md, docs/concepts/exit-codes.md
"""

from pathlib import Path

import duckdb
import pytest
import requests

import src.main as main_module
from src import config
from src.config import DEFAULT_CONFIG_PATH, load_settings
from src.load import TABLE

TEST_TOML = """
[github]
repos = ["owner/repo-a"]

[load]
db_path = "data/test.duckdb"
mode = "append"
"""


@pytest.fixture
def config_path(tmp_path, monkeypatch, sample_repos) -> Path:
    """An isolated setup: temp config, temp database, fake GitHub, no real .env."""
    # Relative paths (and the .env lookup) now point inside tmp_path.
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name in ("GITHUB_ETL_REPOS", "GITHUB_ETL_DB_PATH", "GITHUB_ETL_LOAD_MODE"):
        monkeypatch.delenv(name, raising=False)
    # Patch the names INSIDE src.main: that is where run() looks them up.
    monkeypatch.setattr(main_module, "fetch_repos", lambda settings: sample_repos)
    monkeypatch.setattr(main_module, "save_raw", lambda raw, snapshot_date: None)

    path = tmp_path / "config.toml"
    path.write_text(TEST_TOML, encoding="utf-8")
    return path


def db_file(config_path: Path) -> Path:
    """Where the test database ends up (db_path is relative to PROJECT_ROOT = tmp_path)."""
    return config_path.parent / "data" / "test.duckdb"


# ---------- command-line options ----------


def test_parse_args_defaults():
    args = main_module.parse_args([])

    assert args.config == DEFAULT_CONFIG_PATH
    assert args.mode is None
    assert args.dry_run is False
    assert args.log_level == "INFO"


def test_parse_args_rejects_an_invalid_mode():
    # argparse reports bad options by exiting (SystemExit) with code 2.
    with pytest.raises(SystemExit) as exit_info:
        main_module.parse_args(["--mode", "upsert"])

    assert exit_info.value.code == 2


def test_cli_mode_overrides_the_config(config_path):
    settings = load_settings(config_path)  # mode = "append" in TEST_TOML
    args = main_module.parse_args(["--mode", "overwrite"])

    assert main_module.apply_cli_overrides(settings, args).load_mode == "overwrite"


# ---------- run(): exact counts with the fixed as_of ----------


def test_run_wires_extract_transform_and_load(config_path, as_of):
    summary = main_module.run(load_settings(config_path), as_of)

    # 4 sample repos -> 2 active (A, B) -> 2 rows written
    assert (summary.extracted, summary.active, summary.loaded) == (4, 2, 2)
    with duckdb.connect(str(db_file(config_path)), read_only=True) as con:
        assert con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 2


def test_dry_run_does_not_create_the_database(config_path, as_of):
    summary = main_module.run(load_settings(config_path), as_of, dry_run=True)

    assert summary.loaded == 0
    assert not db_file(config_path).exists()


def test_run_fails_when_nothing_is_extracted(config_path, as_of, monkeypatch):
    monkeypatch.setattr(main_module, "fetch_repos", lambda settings: [])

    with pytest.raises(RuntimeError, match="No repositories"):
        main_module.run(load_settings(config_path), as_of)


# ---------- main(): exit codes (independent of today's date) ----------


def test_main_returns_0_on_success(config_path):
    assert main_module.main(["--config", str(config_path)]) == 0
    assert db_file(config_path).exists()


def test_main_dry_run_returns_0_and_writes_nothing(config_path):
    assert main_module.main(["--config", str(config_path), "--dry-run"]) == 0
    assert not db_file(config_path).exists()


def test_main_returns_1_and_logs_the_error_on_failure(config_path, monkeypatch, caplog):
    def broken_fetch(settings):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(main_module, "fetch_repos", broken_fetch)

    assert main_module.main(["--config", str(config_path)]) == 1
    assert "ETL run failed" in caplog.text
    assert "network down" in caplog.text  # the traceback includes the cause


def test_main_returns_1_for_an_invalid_config(config_path):
    config_path.write_text('[github]\nrepos = ["not-a-valid-name"]\n', encoding="utf-8")

    assert main_module.main(["--config", str(config_path)]) == 1