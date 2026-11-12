# Generators

A function that contains `yield` is a **generator function**. Calling it runs none of its code: it returns a generator object. The body only runs when someone asks for the next value, and it pauses at each `yield` until the next one is requested.

```python
def count_up(n):
    for i in range(n):
        print("producing", i)
        yield i

gen = count_up(3)      # nothing printed yet
next(gen)              # prints "producing 0", returns 0
list(gen)              # runs to the end: [1, 2]
```

When the body finishes, the generator raises `StopIteration`, which `for` loops handle for you.

## Why use them

- **Laziness**: values are produced only when needed. `paginate()` downloads page 2 only after the caller has gone through page 1.
- **Memory**: a generator holds one item at a time, not the whole list.
- **Readable pipelines**: the producer and the consumer stay separate.

## Where they appear in this repo

| Code | What is being generated |
|---|---|
| `extract.paginate()` | repositories, page after page (`yield from items` yields every element of the list) |
| `dlt_pipeline.repo_snapshots()` | a dlt resource is a generator; dlt pulls from it during `pipeline.run()` |
| `main.timed()` | `@contextmanager` turns a one-`yield` generator into a `with` block: code before `yield` runs at the start, code after it at the end |
| `config._env_list()` | `tuple(item.strip() for item in ...)` is a generator **expression**, the comprehension syntax with round brackets |

`list_org_repos()` has no `yield` itself: it returns the generator made by `paginate()`. The type hint `Iterator[RawRepo]` says "something you can loop over that produces repo dicts".

## Gotchas

- **One pass only**: once a generator is used up, looping over it again gives nothing. Call `list(...)` if you need the values twice.
- **Errors come late**: with lazy code, a network error appears while you loop, not when you call `list_org_repos()`. The traceback points at the `for` line.
- Forgetting `yield from` and writing `yield items` yields the whole list as one single item.

## Read more

- https://docs.python.org/3/howto/functional.html#generators
- https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager
