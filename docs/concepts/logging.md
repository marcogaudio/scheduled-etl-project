# Logging

`print()` writes text; `logging` writes **records**. Each record has a time, a severity level and the name of the module that wrote it. You can turn detail up or down without touching the code (`--log-level DEBUG`), and `logger.exception()` includes the full traceback.

A line from a real run:

```
2026-10-31 06:17:04 INFO     src.load: Loaded 6 rows into repo_snapshots (mode=append, replaced 0 existing rows).
```

## Levels

A logger shows records at its level and above: `DEBUG < INFO < WARNING < ERROR < CRITICAL`.

| Level | Used here for |
|---|---|
| DEBUG | every API page and the remaining quota (`extract.paginate`, `_log_quota`) |
| INFO | `START`/`DONE` of each step, row counts, the final summary |
| WARNING | missing token, skipped repository, rate-limit waits, empty load |
| ERROR | `ETL run failed.` with the traceback (`main.main`) |

## Loggers form a tree

Every module does `logger = logging.getLogger(__name__)`, which creates loggers named `src.config`, `src.extract`, and so on. Their records travel up to the **root** logger.

**Only the entry point configures the root logger.** `main.configure_logging()` calls `logging.basicConfig()` with the level and the line format. Modules just use their logger. The `__main__` demo blocks are the only exception, because there the module *is* the entry point.

Libraries have their own loggers too. `urllib3`, the library underneath `requests`, logs every connection at DEBUG, so `configure_logging()` sets it to WARNING to keep `--log-level DEBUG` readable.

## Placeholders, not f-strings

```python
logger.info("Loaded %d rows into %s", df.height, TABLE)
```

The text is only assembled if the record is actually shown, so a DEBUG line costs almost nothing at INFO level. Log tools can also group records by their template.

## Gotchas

- `basicConfig()` does nothing if the root logger already has handlers, for example on a second call or under pytest. `force=True` overrides that, but under pytest it also removes the handlers `caplog` relies on.
- Logs go to **stderr**; `print()` goes to **stdout**. Redirecting one doesn't redirect the other.
- Never log secrets.
- In tests, the `caplog` fixture captures records: `assert "ETL run failed" in caplog.text`.

## Read more

- https://docs.python.org/3/howto/logging.html
