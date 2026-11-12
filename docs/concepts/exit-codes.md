# Exit codes and error handling

## Exit codes

Every program ends by handing a number back to whatever started it: `0` means success, anything else means failure. Shells, cron and CI systems decide what to do next based on that number alone.

```bash
python -m src.main ; echo $?        # macOS/Linux
python -m src.main ; $LASTEXITCODE  # PowerShell
```

| Code | Here |
|---|---|
| `0` | the run finished |
| `1` | something raised during the run; the log has the traceback |
| `2` | invalid command-line option (set by argparse) |

- `if __name__ == "__main__": sys.exit(main())`: `main()` returns an int, and `sys.exit` turns it into the exit code.
- `raise SystemExit("message")` in the demo blocks prints the message to stderr and exits with `1`.
- In GitHub Actions, a step that exits non-zero fails. The following steps are skipped, the run turns red, and you get an e-mail. A failed run therefore never saves a broken database to the cache.

## Where errors are caught

Catch an exception only where you can do something useful with it. Otherwise, let it travel up.

- **`extract.fetch_repos()`** catches `requests.HTTPError`. A 404 for one repo means a typo or a deleted repo, so it logs a warning and continues. Any other status is re-raised with a bare `raise`, which keeps the original traceback.
- **`load.write_snapshot()`** catches everything only to run `ROLLBACK`, then re-raises. `finally` unregisters the DataFrame whether or not something failed.
- **`main.main()`** has the only `except Exception` that doesn't re-raise. It's the top of the program, so it logs the error with `logger.exception()` and returns `1`.

`Ctrl+C` raises `KeyboardInterrupt`, which inherits from `BaseException`, not `Exception`. It isn't caught, so the program stops right away, as it should.

## Raising useful errors

- **Fail fast**: `config._validate()` raises a `ValueError` naming the bad setting before any API call is made.
- **Custom exceptions**: `class RateLimitError(RuntimeError)` lets callers catch rate-limit problems specifically.
- **`raise ... from None`** (in `_env_int`) hides the original `int()` error when the new message already says everything. `raise NewError(...) from err` would keep both in the traceback.
- **An empty run is a failed run**: if extract returns zero repositories, `run()` raises `RuntimeError`. Zero repos almost always means a broken config, and a red run is better than a silent empty day.

## Read more

- https://docs.python.org/3/tutorial/errors.html
- https://en.wikipedia.org/wiki/Exit_status
