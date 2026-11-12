# HTTP and REST APIs

Every call to the GitHub API is an **HTTP request**, and GitHub sends back an **HTTP response**. You can see both with curl:

```bash
curl -i https://api.github.com/repos/pola-rs/polars
```

## Anatomy

A request has:
- a **method**: `GET` reads, `POST` creates, `PATCH` changes, `DELETE` removes. This project only uses `GET`.
- a **URL**, optionally with a **query string** after `?`: `/orgs/dlt-hub/repos?type=public&per_page=100`
- **headers**: key/value metadata, such as the token, the response format you want, and who is asking

A response has:
- a **status code**
- headers: rate-limit counters, the link to the next page
- a **body**: here always JSON, which `response.json()` turns into Python dicts and lists

| Status | Meaning | What the code does |
|---|---|---|
| 200 | OK | uses the JSON |
| 301 | moved (a renamed repo) | `requests` follows the redirect on its own |
| 401 | bad or expired token | raises: fix `GITHUB_TOKEN` |
| 403 | rate limit **or** no permission | rate limit: wait and retry. Otherwise: raise |
| 404 | not found, or private | single repo: warn and skip. Otherwise: raise |
| 429 | too many requests | wait and retry |
| 5xx | problem on GitHub's side | retried automatically with backoff |

The rule of thumb: 2xx success, 3xx go elsewhere, 4xx your request is wrong, 5xx the server is having a bad day.

## REST

REST is a style of API design: every thing (a repo, an organisation's list of repos) has its own URL, and the HTTP method says what to do with it. The three endpoints used here:

| Config key | Endpoint | Returns |
|---|---|---|
| `github.repos` | `GET /repos/{owner}/{name}` | one repo object |
| `github.orgs` | `GET /orgs/{org}/repos?type=public` | a paginated list |
| `github.users` | `GET /users/{user}/repos?type=owner` | a paginated list |

## Headers sent with every request (`extract.DEFAULT_HEADERS`)

- `Accept: application/vnd.github+json`: GitHub's recommended response format.
- `X-GitHub-Api-Version: 2022-11-28`: pins the API version, so a future change on GitHub's side doesn't silently change the responses. It's the same idea as pinning a library version.
- `User-Agent: github-etl-learning-project`: GitHub rejects requests without one.
- `Authorization: Bearer <token>`: only when a token is set. "Bearer" means whoever holds the token is allowed in.

## Things in the JSON that matter later

- `license` and `language` can be `null`.
- Timestamps are text in ISO 8601 format, e.g. `"2026-10-30T18:55:01Z"`.
- `open_issues_count` also counts open pull requests.
- `watchers_count` is just a copy of `stargazers_count`, for historical reasons.

## Read more

- https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
- https://docs.github.com/en/rest/repos/repos
- https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
