"""Unit tests for src/config.py.

Each test writes a small TOML file into pytest's temporary folder (tmp_path)
and sets environment variables with monkeypatch, which undoes every change
after the test. Your real config/config.toml and .env are never used.
"""

from pathlib import Path

import pytest

from src import config
from src.config import load_settings

PIPELINE_ENV_VARS = [
    "GITHUB_TOKEN",
    "GITHUB_ETL_REPOS",
    "GITHUB_ETL_ORGS",
    "GITHUB_ETL_USERS",
    "GITHUB_ETL_PER_PAGE",
    "GITHUB_ETL_ACTIVE_MAX_DAYS",
    "GITHUB_ETL_DB_PATH",
    "GITHUB_ETL_LOAD_MODE",
]

MINIMAL_TOML = """
[github]
repos = ["pola-rs/polars"]
"""


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Give every test in this file a clean environment.

    autouse=True applies the fixture to every test automatically.
    - Removes the pipeline's variables that may be set on your machine.
    - Points PROJECT_ROOT at the empty temp folder, so your real .env is not loaded
      and relative paths resolve inside tmp_path.
    """
    for name in PIPELINE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)  # raising=False: fine if it wasn't set
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)


def write_config(tmp_path: Path, text: str) -> Path:
    """Write a TOML file into the temp folder and return its path."""
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_fill_missing_values(tmp_path):
    settings = load_settings(write_config(tmp_path, MINIMAL_TOML))

    assert settings.repos == ("pola-rs/polars",)
    assert settings.per_page == 100
    assert settings.active_max_days_since_push == 365
    assert settings.load_mode == "append"
    assert settings.db_path == tmp_path / "data" / "output.duckdb"
    assert settings.has_token is False


def test_config_file_beats_defaults(tmp_path):
    toml = MINIMAL_TOML + 'per_page = 50\n[load]\nmode = "overwrite"\n'

    settings = load_settings(write_config(tmp_path, toml))

    assert settings.per_page == 50
    assert settings.load_mode == "overwrite"


def test_environment_beats_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ETL_REPOS", "a/b, c/d")
    monkeypatch.setenv("GITHUB_ETL_LOAD_MODE", "overwrite")

    settings = load_settings(write_config(tmp_path, MINIMAL_TOML))

    assert settings.repos == ("a/b", "c/d")
    assert settings.load_mode == "overwrite"


def test_empty_environment_variable_counts_as_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ETL_REPOS", "")

    settings = load_settings(write_config(tmp_path, MINIMAL_TOML))

    assert settings.repos == ("pola-rs/polars",)


def test_token_is_loaded_but_never_printed(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "github_pat_secret123")

    settings = load_settings(write_config(tmp_path, MINIMAL_TOML))

    assert settings.has_token is True
    assert "secret123" not in repr(settings)


def test_missing_token_logs_a_warning(tmp_path, caplog):
    load_settings(write_config(tmp_path, MINIMAL_TOML))

    assert "GITHUB_TOKEN is not set" in caplog.text


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ('[github]\nrepos = ["not-a-valid-name"]\n', "owner/name"),
        ("[github]\nrepos = []\n", "Nothing to fetch"),
        ('[github]\nrepos = ["a/b"]\nper_page = 500\n', "per_page"),
        ('[github]\nrepos = ["a/b"]\n[load]\nmode = "apend"\n', "load.mode"),
    ],
)
def test_invalid_settings_raise_clear_errors(tmp_path, toml, message):
    with pytest.raises(ValueError, match=message):
        load_settings(write_config(tmp_path, toml))


def test_non_numeric_environment_variable_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ETL_PER_PAGE", "abc")

    with pytest.raises(ValueError, match="whole number"):
        load_settings(write_config(tmp_path, MINIMAL_TOML))