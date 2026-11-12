# Pure functions

A function is **pure** when:
1. its result depends only on its arguments: same input, same output, every time
2. it has no **side effects**: it doesn't change anything outside itself (files, databases, globals, its own inputs) and it doesn't read hidden inputs like the clock or the network

```python
def add_derived(df, as_of):          # pure: everything it needs is a parameter
    ...

def add_derived_impure(df):
    now = datetime.now(timezone.utc) # hidden input: the result changes every second
    ...
```

## Why it matters here

The functions in `src/transform.py` (`to_frame`, `clean`, `add_derived`, `filter_active`) are pure, and that's what makes them easy to test:
- `tests/conftest.py` fixes `as_of` at 2026-10-31 12:00 UTC, so "days since last push" for a repo pushed on 2026-09-01 is always exactly 60, whatever day you run the tests.
- No network, no files, no setup and no cleanup.
- `test_transform_does_not_modify_its_input` checks the "doesn't change its inputs" half directly.

Passing the clock in as `as_of` instead of reading it inside is a small case of **dependency injection**: the caller provides what the function depends on.

`transform()` itself writes one log line. Strictly speaking that's a side effect, but a harmless one, because it can't change the result.

## Functional core, imperative shell

The whole project follows one pattern:
- **Imperative shell**: the code that talks to the outside world. `extract.py` (network), `load.py` (database), `main.py` (clock, command line, exit code). It's tested with fakes: `responses`, temporary folders, `monkeypatch`.
- **Functional core**: the logic in between, `transform.py`, kept pure. It's tested with plain inputs and outputs.

The more logic sits in the core, the less code needs fakes to test.

## Read more

- https://en.wikipedia.org/wiki/Pure_function
- https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell
