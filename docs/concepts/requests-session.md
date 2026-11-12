# requests: sessions, timeouts, retries

`requests` is the standard library for HTTP in Python, although it isn't in the standard library itself. `requests.get(url)` is enough for a one-off call. A pipeline that makes many calls to the same server needs three more things, all set up in `extract.make_session()`.

## Session

```python
with make_session(settings.github_token) as session:
    session.get(url, params=params, timeout=REQUEST_TIMEOUT)
```

A `requests.Session` keeps the TCP connection open between requests (**connection pooling**), so it doesn't pay for a new handshake every time. It also remembers headers, so the token and `Accept` header are set once. Using it in a `with` block closes the connections at the end, even if an error happens.

## Timeouts

`requests` has **no default timeout**. If GitHub accepts the connection and then never answers, the call waits forever, and a scheduled job just hangs until GitHub Actions kills it after `timeout-minutes`.

`REQUEST_TIMEOUT = (10, 30)` means: up to 10 seconds to connect, and up to 30 seconds waiting for data. A timeout raises `requests.Timeout`, which `main()` reports as a failed run.

## raise_for_status

`requests` doesn't raise on a 404 or a 500; it just gives you the response. `response.raise_for_status()` turns any 4xx or 5xx into a `requests.HTTPError` that carries the response (`error.response.status_code`). `fetch_repos()` uses that to tell a missing repo (404) apart from everything else.

## Automatic retries

Some failures are temporary: a 502 from an overloaded proxy, a 503 during a deploy. Retrying a moment later usually works.

```python
retry = Retry(total=3, backoff_factor=1, status_forcelist=(500, 502, 503, 504),
              allowed_methods=("GET",), raise_on_status=False)
session.mount("https://", HTTPAdapter(max_retries=retry))
```

- `Retry` comes from `urllib3`, the library `requests` is built on. An `HTTPAdapter` attaches it to every `https://` URL the session calls.
- The waits grow exponentially, roughly 1 s, 2 s, 4 s: this is **exponential backoff**.
- Only `GET` is retried. It's safe to repeat because it doesn't change anything on the server.
- `raise_on_status=False` hands the last error response back, so `raise_for_status()` produces the usual error.

Rate-limit answers (403/429) are deliberately **not** in that list. They need a different wait, computed from the response headers. See [rate limiting](rate-limiting.md).

## The dlt version

`dlt_pipeline.make_client()` builds dlt's `RESTClient` instead. Base URL, headers, `BearerTokenAuth` and retries are all handled by dlt, and `HeaderLinkPaginator` replaces the hand-written pagination. Comparing `make_client()` with `make_session()` + `paginate()` shows exactly what the library saves you from writing.

## Read more

- https://requests.readthedocs.io/en/latest/user/advanced/
- https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html
