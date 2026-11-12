# Command-line options with argparse

The words typed after a command end up in `sys.argv` as a list of strings. `argparse` (standard library) turns that list into an object with one attribute per option, rejects invalid values and generates `--help`.

```python
parser.add_argument("--mode", choices=VALID_LOAD_MODES, default=None)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--log-level", choices=LOG_LEVELS, default="INFO")
args = parser.parse_args(argv)
args.dry_run      # dashes become underscores
```

| Option | Default | Effect |
|---|---|---|
| `--config PATH` | `config/config.toml` | read another TOML file |
| `--mode {append,overwrite}` | from the config | override `load.mode` for this run only |
| `--dry-run` | off | extract and transform, write nothing |
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | `INFO` | amount of logging |
| `--engine {manual,dlt}` | `manual` | hand-written or dlt extract/load |

## Details worth knowing

- `choices` rejects anything else: `--mode upsert` prints the usage and exits with code **2**, the convention for "called wrong".
- `action="store_true"` makes a flag without a value: present means `True`, absent means `False`.
- `type=Path` converts the typed text into a `pathlib.Path`.
- `--mode` defaults to `None`, meaning "not given", so the value from the config file survives. `apply_cli_overrides()` only replaces it when the option was actually used. Full priority: command line, environment, file, defaults.
- `parse_args(argv)` takes the list as a parameter. `None` means the real `sys.argv[1:]`, while tests pass their own: `main(["--config", path, "--dry-run"])`.

## Gotchas

- Every attribute the code reads must be declared. If an `add_argument` is deleted, or placed *after* `return parser.parse_args(argv)` where it never runs, you get `AttributeError: 'Namespace' object has no attribute 'log_level'`. This happened in this repo when `--engine` was added. To check what's declared:

  ```bash
  python -c "import src.main as m; print(m.parse_args([]))"
  ```

- On an error, argparse raises `SystemExit`. Tests check it with `pytest.raises(SystemExit)` and look at `.code == 2`.

## Read more

- https://docs.python.org/3/howto/argparse.html
- https://docs.python.org/3/library/argparse.html
