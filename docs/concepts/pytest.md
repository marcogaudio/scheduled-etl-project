# pytest

A **unit test** runs one small piece of code on a known input and checks the result. The suite here has 70 of them. They:
- catch mistakes as soon as you make them
- tell you whether a refactor broke something
- run in CI before every scheduled ETL, so broken code never reaches the database

## How pytest finds and runs tests

- **Discovery**: files named `test_*.py`, and inside them functions named `test_*`.
- **Plain `assert`**: `assert result == expected`. When it fails, pytest rewrites the assertion to show both values and the difference.
- **Exit code**: `0` if everything passed. GitHub Actions uses that to stop the job.

```bash
pytest -v                          # one line per test
pytest tests/test_transform.py     # one file
pytest -k filter_active            # tests whose name contains "filter_active"
pytest -x                          # stop at the first failure
pytest --lf                        # re-run only what failed last time
```

`tests/` has an `__init__.py`, so pytest puts the project root on `sys.path` and `from src.transform import ...` works. See [entry points](entry-points.md).

## Arrange, Act, Assert

```python
def test_clean_fills_missing_labels(make_repo):
    df = clean(to_frame([make_repo(license=None, language=None)]))   # arrange + act
    assert df["license_spdx"].to_list() == [NO_LICENSE]               # assert
    assert df["language"].to_list() == [UNKNOWN_LANGUAGE]
```

## Tools used in this suite

- **`@pytest.mark.parametrize`** runs one test function on many inputs, each reported separately. `test_filter_active` covers 7 cases: active, archived, disabled, stale, never pushed, and the two boundary cases.
- **`pytest.raises(ValueError, match="timezone-aware")`** passes only if that error is raised inside the `with` block. `match` is a regular expression searched in the message.
- **`polars.testing.assert_frame_equal(a, b)`** compares two DataFrames: values, dtypes and column order. `==` doesn't work for that.
- **[Fixtures](pytest-fixtures.md)** for shared test data, [monkeypatch](monkeypatch.md) for temporary changes, and [responses](mocking-http.md) to fake GitHub.

## Choosing test cases

- **Boundary values**: bugs hide at the edges. `filter_active` keeps a repo pushed exactly 365 days ago and drops one pushed 366 days ago. A `<` typed instead of `<=` only shows up there.
- **Empty input**: `transform([])` must return an empty table with all the columns, not crash.
- **Missing data**: `license: null`, `forks_count: 0`, `pushed_at: null`.
- **No dependence on today's date**: tests use the fixed `as_of`. The `main()` tests that use the real clock only check exit codes, never counts that change over time.

## A useful exercise

Change `<=` to `<` in `filter_active()` and run `pytest -k filter_active`. Exactly the 365-day case fails. Breaking code on purpose to see whether the tests notice is the idea behind **mutation testing**.

## Read more

- https://docs.pytest.org/en/stable/getting-started.html
- https://docs.pytest.org/en/stable/how-to/parametrize.html
