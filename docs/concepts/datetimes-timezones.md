# Dates, times and time zones

## Naive and aware

A Python `datetime` is either:
- **naive**: no time zone. `datetime(2026, 10, 31, 12, 0)` could be noon anywhere on Earth.
- **aware**: has a time zone. `datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)` is one exact instant.

Comparing or subtracting a naive and an aware datetime raises an error, or silently gives the wrong answer if you mix up zones. `transform()` refuses a naive `as_of` with a clear `ValueError`.

## UTC everywhere

**UTC** has no daylight saving time and is the same for everyone, so this project uses it for everything:
- GitHub's timestamps: the `Z` at the end of `2026-10-30T18:55:01Z` means UTC.
- the run time: `datetime.now(timezone.utc)` in `main()`
- `snapshot_date`
- the cron schedule in GitHub Actions: 06:17 UTC is 07:17 in Rome in winter and 08:17 in summer

Convert to local time only when showing data to a person.

## Formats

- **ISO 8601**: `2026-10-30T18:55:01Z`, readable and sortable as text. GitHub sends it, `date.isoformat()` produces it (`2026-10-31`), and that's why the raw files sort by name.
- **Unix timestamp**: seconds since 1970-01-01 00:00 UTC, e.g. `1793427600`. It's compact and has no time zone to worry about. GitHub's `X-RateLimit-Reset` header uses it, and `time.time()` returns it.

## One timestamp per run

`main()` calls `datetime.now(timezone.utc)` **once** and passes it to every step as `as_of`:
- `snapshot_date` and every "days since" value come from the same instant, even if the run happens to cross midnight.
- The transform never reads the clock itself, so tests can pass a fixed `as_of` and get exact results. See [pure functions](pure-functions.md).

## Durations and day counts

`as_of - pushed_at` is a duration. `.dt.total_days()` keeps whole days, rounded down: 17 hours counts as 0 days. In the tests, Python's own `(as_of - created).days` cross-checks the Polars result.

## Gotchas

- `datetime.utcnow()` returns a **naive** datetime even though it's UTC; it's deprecated for that reason. Use `datetime.now(timezone.utc)`.
- DuckDB may *display* `TIMESTAMPTZ` values in your computer's time zone, e.g. `2026-10-30 19:55:01+01`. It's the same instant as `18:55:01Z`; only the display differs.
- A day missing from the history can never be recovered: the API only gives today's star count. That's why the job runs daily.

## Read more

- https://docs.python.org/3/library/datetime.html#aware-and-naive-objects
- https://en.wikipedia.org/wiki/ISO_8601
