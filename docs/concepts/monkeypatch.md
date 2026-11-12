# monkeypatch

`monkeypatch` is a built-in pytest fixture that changes things temporarily during a test and **undoes every change automatically** when the test ends, even if it fails.

| Call | Does | Used in |
|---|---|---|
| `monkeypatch.setenv(name, value)` | set an environment variable | `test_config.py`: `GITHUB_ETL_REPOS="a/b, c/d"` |
| `monkeypatch.delenv(name, raising=False)` | remove one (no error if it isn't set) | `test_config.py`, `test_main.py` |
| `monkeypatch.setattr(obj, "name", value)` | replace an attribute or function | all of the below |

## What gets replaced in this repo

- **`config.PROJECT_ROOT` → `tmp_path`**: relative paths and the `.env` lookup point into an empty temporary folder, so your real `.env` and `data/` are never touched.
- **`extract.time.sleep` → `sleeps.append`**: the rate-limit test records the wait it would have done, instead of sleeping for 30 seconds.
- **`main_module.fetch_repos` → `lambda settings: sample_repos`**: `run()` gets fake repositories without calling GitHub.
- **`main_module.save_raw` → a function that does nothing**: no files are written to `data/raw/`.

## Patch where the name is looked up

`src/main.py` does `from src.extract import fetch_repos`. That line creates a **second name**, `src.main.fetch_repos`, pointing at the same function. `run()` looks the function up in its own module.

```python
monkeypatch.setattr(main_module, "fetch_repos", fake)        # works: run() sees the fake
monkeypatch.setattr(src.extract, "fetch_repos", fake)        # no effect on run()
```

Patching the original module only changes the original name; `main.py` still holds the real function. The rule ("patch where it's used, not where it's defined") is the same for `unittest.mock.patch`.

`extract.time.sleep` works the other way round. `extract.py` does `import time` and calls `time.sleep(...)`, looking up `sleep` on the `time` module each time, so the patch goes on the module itself.

## Read more

- https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- https://docs.python.org/3/library/unittest.mock.html#where-to-patch
