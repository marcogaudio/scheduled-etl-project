# Dataclasses and type hints

`@dataclass` writes the boilerplate methods (`__init__`, `__repr__`, `__eq__`) for you, based on the class's annotated fields.

```python
@dataclass(frozen=True)
class Settings:
    repos: tuple[str, ...]
    orgs: tuple[str, ...]
    users: tuple[str, ...]
    per_page: int
    active_max_days_since_push: int
    db_path: Path
    load_mode: str
    github_token: str | None = field(default=None, repr=False)
```

Compared with a nested dict, `settings.repos` fails immediately on a typo and the editor can autocomplete it. `config["github"]["repos"]` fails with a `KeyError` somewhere in the middle of a run.

## The options used here

- **`frozen=True`**: assigning to a field raises `FrozenInstanceError`, so no code can change the settings halfway through a run. Frozen instances are also hashable.
- **Tuples instead of lists**: `frozen` only blocks *reassigning* a field. A list field could still be changed with `.append()`, while a tuple can't be modified at all. (Dataclasses also refuse a mutable default like `= []`; you'd need `field(default_factory=list)`.)
- **`field(repr=False)`**: leaves the token out of the generated `__repr__`, so `print(settings)` and the logs never show it. Gotcha: `dataclasses.asdict(settings)` still includes it.
- **`@property`**: `has_token` is computed when you read it and used without parentheses: `settings.has_token`.
- **`dataclasses.replace()`**: you can't change a frozen object, but you can copy it with one field different. `main.apply_cli_overrides()` uses `replace(settings, load_mode=args.mode)` for `--mode`.

`RunSummary` in `src/main.py` is another frozen dataclass, used as a return value. `summary.loaded` is clearer than `summary[3]` would be with a tuple.

## Type hints

`str | None`, `tuple[str, ...]` (a tuple of any length), `dict[str, Any]`, `-> Settings`. They document what goes in and out, and editors and type checkers (mypy) use them.

**Python does not check them at runtime.** `Settings(per_page="100", ...)` is accepted without complaint, which is why `load_settings()` validates the values itself.

`RawRepo = dict[str, Any]` in `extract.py` and `transform.py` is a **type alias**: a readable name for a longer type.

## Read more

- https://docs.python.org/3/library/dataclasses.html
- https://docs.python.org/3/library/typing.html
