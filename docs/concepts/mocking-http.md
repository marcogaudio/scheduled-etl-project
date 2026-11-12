# Faking HTTP in tests

Tests that call the real GitHub API are:
- **slow**: network round trips
- **flaky**: they fail when the network or GitHub has a bad moment
- **unstable**: star counts change every day, so exact assertions break
- **costly**: they use up the rate limit

They also can't easily produce the cases that matter most: a 404, a rate-limit answer, a second page. So the tests in `test_extract.py` and `test_dlt_pipeline.py` replace GitHub with a fake.

## The `responses` library

`responses` intercepts every request made through `requests` and answers with the responses registered in the test:

```python
@responses.activate                       # interception on, for this test only
def test_missing_repo_is_skipped_with_a_warning(caplog):
    responses.add(responses.GET, f"{API_URL}/repos/acme/tool", json={"id": 1, "full_name": "acme/tool"})
    responses.add(responses.GET, f"{API_URL}/repos/acme/typo", json={"message": "Not Found"}, status=404)

    result = fetch_repos(make_settings(repos=["acme/tool", "acme/typo"]))

    assert [r["id"] for r in result] == [1]
```

- **A request to an unregistered URL raises an error**, so a test can never reach the internet by accident.
- **The same URL registered twice is answered in order**: first a 403 rate limit, then a 200. That's how the wait-and-retry logic is tested.
- **`responses.calls`** lists the requests that were made: count the pages, or read the headers (`calls[0].request.headers["Authorization"]`).
- **It works for dlt too**: dlt's `RESTClient` is built on `requests`, so the same fakes cover `extract_with_dlt()`.
- **Retries aren't exercised**: `responses` sits above urllib3, so the automatic 5xx retries in `make_session()` don't run in these tests.

## Test doubles, in general

A test double is anything that stands in for a real dependency. The usual names:

| Name | What it is | Example here |
|---|---|---|
| fake | a working, simplified implementation | `responses` acting as GitHub; a DuckDB file in `tmp_path` |
| stub | returns canned answers | `lambda settings: sample_repos` instead of `fetch_repos` |
| spy | records how it was called | `sleeps.append` instead of `time.sleep` |
| mock | checks it was called in a specific way | `unittest.mock.Mock` with `assert_called_once_with` |

Other libraries with the same purpose: `vcrpy` records real responses once and replays them; `pytest-httpserver` runs a real local server.

## Read more

- https://github.com/getsentry/responses
- https://martinfowler.com/articles/mocksArentStubs.html
