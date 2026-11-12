# Rate limiting and backoff

APIs limit how many requests a client can make in a time window, to protect themselves from bugs and abuse.

| Who is asking | GitHub REST limit |
|---|---|
| no token | 60 requests per hour (per IP address) |
| personal access token | 5,000 per hour |
| `GITHUB_TOKEN` inside GitHub Actions | 1,000 per hour per repository |

The default config makes 6 requests per run, so the limits are far away. The handling below is a safety net, and a required part of the project.

## Reading the limit

Every response tells you where you stand:

```bash
curl -sI https://api.github.com/repos/pola-rs/polars | grep -i ratelimit
# x-ratelimit-limit: 60
# x-ratelimit-remaining: 57
# x-ratelimit-reset: 1793427600      <- Unix timestamp: seconds since 1970-01-01 UTC
```

`GET https://api.github.com/rate_limit` shows the same numbers and doesn't count against the limit.

GitHub has two kinds of limit:
- **Primary**: the hourly quota is used up. The answer is 403 or 429 with `X-RateLimit-Remaining: 0`, and you wait until `X-RateLimit-Reset`.
- **Secondary**: too many requests too fast, or too many at once. The answer is 403 or 429, sometimes with a `Retry-After: <seconds>` header.

## How the code reacts (`src/extract.py`)

The strategy is reactive: send the request normally, and only if GitHub refuses because of a limit, wait and try again.

1. `_is_rate_limited()` decides whether a response is a rate limit. A 429 always is. A 403 is only if it has `X-RateLimit-Remaining: 0`, a `Retry-After` header, or "rate limit" in the message. A plain 403 is a real permission error and must not be retried.
2. `_seconds_to_wait()` follows GitHub's documented order:
   - `Retry-After` if present;
   - otherwise the reset time minus now, plus 1 second of margin;
   - otherwise 60 seconds.
3. `_get()` sleeps and retries, at most 3 times. If the wait would be longer than 15 minutes, it raises `RateLimitError` instead. Sleeping for an hour in CI helps nobody.
4. `_log_quota()` logs the remaining quota at DEBUG and warns below 10.

## Backoff, in general

Retrying a failed request immediately usually fails again, and many clients retrying at the same moment can keep a recovering server down (a "thundering herd"). The standard fixes:

- **Exponential backoff**: wait 1 s, 2 s, 4 s, 8 s… This is what the `urllib3.Retry` in `make_session()` does for 5xx errors.
- **Jitter**: add a random amount to each wait, so clients spread out. Not needed for one daily job, but common in services.
- **A cap**: on the number of attempts and on the total wait.

## Testing it

`test_rate_limit_waits_until_reset_then_retries` registers a fake 403 with `X-RateLimit-Remaining: 0`, followed by a 200. It replaces `time.sleep` with a function that records the requested wait, so the test checks the computed wait without actually waiting.

## Read more

- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- https://en.wikipedia.org/wiki/Unix_time
