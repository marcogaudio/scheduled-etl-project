# pathlib

`pathlib.Path` represents a file path as an object instead of a string. The `/` operator joins parts, and the same code works on macOS, Linux and Windows.

| Code | Where | What it does |
|---|---|---|
| `Path(__file__).resolve().parent.parent` | `config.PROJECT_ROOT` | absolute path of the project root (`__file__` is `src/config.py`) |
| `PROJECT_ROOT / "config" / "config.toml"` | `config.DEFAULT_CONFIG_PATH` | joins path parts |
| `path.is_absolute()` | `config._resolve_path()` | checks whether a path is absolute |
| `directory.mkdir(parents=True, exist_ok=True)` | `extract.save_raw()`, `load.connect()` | creates the folder and any missing parents; no error if it exists |
| `path.write_text(text, encoding="utf-8")` | `extract.save_raw()` | writes a whole file at once |
| `sorted(folder.glob("*.json"))` | demo blocks in `transform.py`, `load.py` | lists files matching a pattern. File names are dates, so sorting puts the newest last |
| `directory.as_posix()` | `load.export_parquet()` | the path with forward slashes, safe to put inside SQL |

## Why paths are anchored to the project root

A relative path like `data/output.duckdb` is relative to the **current working directory**: the folder you launched the command from, not the folder the code is in. Run from another folder and you'd silently get a second, empty database somewhere else.

`_resolve_path()` joins every relative path from the config to `PROJECT_ROOT`, so the same file is used wherever the command starts. Absolute paths are left as they are.

## Gotchas

- Always pass `encoding="utf-8"` to `read_text`/`write_text`. The default depends on the operating system (Windows often uses cp1252), and JSON with non-English characters breaks.
- Some libraries want a string: `duckdb.connect(str(db_path))`.
- `__file__` doesn't exist in a notebook or the interactive prompt.

## Read more

- https://docs.python.org/3/library/pathlib.html
