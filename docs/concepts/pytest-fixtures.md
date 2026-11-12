# pytest fixtures

A **fixture** prepares something a test needs: data, a temporary folder, a fake. A test asks for it by **naming it as a parameter**, and pytest calls the fixture and passes in the result.

```python
@pytest.fixture
def as_of() -> datetime:
    return datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

def test_snapshot_date_is_the_run_date(make_repo, as_of):   # pytest injects both
    ...
```

## conftest.py

Fixtures in `tests/conftest.py` are available to every test file without an import. This repo's:

| Fixture | Gives |
|---|---|
| `as_of` | the fixed run time, 2026-10-31 12:00 UTC |
| `make_repo` | a *function* that builds a fake GitHub repo dict |
| `sample_repos` | four repos: two active, one stale, one archived |

**`make_repo` is a factory fixture.** It returns a function instead of data, so each test changes only what matters to it: `make_repo(forks_count=0)`, `make_repo(archived=True)`. Every other field keeps a sensible default.

**Fixtures can use fixtures.** `sample_repos(make_repo)` builds its list with `make_repo`. In `test_load.py`, `day1_df(sample_repos, as_of)` builds on both.

## Options

- **Scope**: by default a fixture runs again for every test (`scope="function"`), so tests can't affect each other. `scope="module"` or `"session"` shares one result. That's faster, but a test that modifies it affects the others.
- **`autouse=True`**: applies to every test in the file without being named. `test_config.py` uses it for `isolated_environment`, which removes the pipeline's environment variables and points `PROJECT_ROOT` at a temporary folder, so your real `.env` is never read.
- **Teardown with `yield`**: code after `yield` runs when the test finishes, for cleanup. Not needed here, because the built-in fixtures clean up after themselves.

## Built-in fixtures used here

| Fixture | Gives |
|---|---|
| `tmp_path` | a fresh empty folder (`pathlib.Path`) for each test. All test databases live there |
| `monkeypatch` | temporary changes to attributes and environment variables. See [monkeypatch](monkeypatch.md) |
| `caplog` | the log records written during the test: `"acme/typo" in caplog.text` |

## Read more

- https://docs.pytest.org/en/stable/how-to/fixtures.html
- https://docs.pytest.org/en/stable/reference/fixtures.html
