# Pagination

An API can't return 6,000 repositories in one response: it would be slow and huge. It sends them in **pages**, and you ask for the next one until there are no more.

## Three common styles

| Style | You send | Problem |
|---|---|---|
| page number | `?page=3&per_page=100` | if items are added while you read, rows shift and you get duplicates or gaps |
| offset | `?offset=200&limit=100` | same problem, and slow on big tables |
| cursor / next link | the token or URL the previous page gave you | none of the above; you can't jump to page 50 |

GitHub mixes the first and third: page numbers in the URL, but it **gives you the next URL** in a `Link` header, so you never build it yourself:

```
Link: <https://api.github.com/organizations/123/repos?page=2&per_page=100>; rel="next",
      <https://api.github.com/organizations/123/repos?page=7&per_page=100>; rel="last"
```

`requests` parses this header for you: `response.links["next"]["url"]`.

## In this repo: `extract.paginate()`

```python
next_url = url
while next_url:
    response = _get(session, next_url, params=params)
    yield from response.json()                              # hand out this page's repos
    next_url = response.links.get("next", {}).get("url")    # None on the last page
    params = None                                           # the next URL already has them
```

- `per_page=100` is GitHub's maximum, so it means the fewest requests. An organisation with 250 repositories takes 3 calls.
- The query parameters are sent only with the first request. Sending them again with the "next" URL would duplicate `per_page`.
- `paginate()` is a [generator](generators.md): it downloads page 2 only when the caller has consumed page 1.

In the dlt version, `HeaderLinkPaginator()` does the same, and `client.paginate()` yields one page (a list of repos) at a time.

## Gotchas

- Forgetting the last page: the loop must stop when `next` is missing, not when a page is "short".
- A page can be empty. `yield from []` simply yields nothing.
- The test `test_pagination_follows_the_link_header` fakes two pages with `responses` and checks that exactly two requests were made.

## Read more

- https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
