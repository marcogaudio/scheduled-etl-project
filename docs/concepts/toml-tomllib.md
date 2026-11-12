# TOML configuration

TOML is a configuration format built to be easy for people to read. It has `[sections]`, `key = value` lines and `#` comments. Strings are quoted, lists go in `[ ]`, and numbers and booleans are written bare. Every TOML file maps directly onto a Python dict:

```toml
[load]
db_path = "data/output.duckdb"
mode = "append"
```

```python
{"load": {"db_path": "data/output.duckdb", "mode": "append"}}
```

Why TOML and not the alternatives:
- JSON has no comments, and every comment in `config/config.toml` explains a setting.
- YAML has surprising rules. In YAML 1.1 the bare word `no` means `false`, so a country code like `NO` (Norway) silently turns into a boolean.

Python's own `pyproject.toml` uses TOML.

## tomllib

`tomllib` is in the standard library since Python 3.11. It can only **read** TOML. It needs the file opened in binary mode:

```python
with Path(config_path).open("rb") as f:
    config = tomllib.load(f)
```

A syntax error raises `tomllib.TOMLDecodeError` with the line number.

## How the settings are built (`src/config.py`)

Every setting is looked up in three places. `_pick(env_value, file_value, default)` returns the first one that isn't `None`:

1. environment variable (`GITHUB_ETL_LOAD_MODE`)
2. config file (`[load] mode`)
3. default constant (`DEFAULT_LOAD_MODE`)

`src/main.py` then applies command-line options on top (`--mode`). A missing section doesn't crash anything, because `config.get("github", {})` falls back to an empty dict.

After merging, `_validate()` checks the values and stops with a precise message: nothing to fetch, a repo not written `owner/name`, `per_page` outside 1 to 100, a non-positive day threshold, an unknown mode. This is **fail fast**: a typo costs one second and one clear error, instead of a confusing failure after minutes of API calls.

## Gotchas

- `repos = "a/b"` (a string instead of a list) gets split into single characters by `tuple(...)`. Validation catches it as an invalid repo name.
- Secrets never go in TOML. See [environment variables](environment-variables.md).

## Read more

- https://toml.io/en/
- https://docs.python.org/3/library/tomllib.html
