# Polars expressions

An **expression** describes a computation on columns without running it:

```python
pl.col("stargazers_count") / pl.col("forks_count")
```

That line computes nothing. It becomes work only inside a **context**: `select`, `with_columns`, `filter` or `group_by().agg()`. Because Polars sees all the expressions of a call at once, it can run them in parallel and skip work it doesn't need.

| Context | Does | Example here |
|---|---|---|
| `select(...)` | keep or compute only these columns | `.select(OUTPUT_COLUMNS)` |
| `with_columns(...)` | add or replace columns, keep the rest | `clean()`, `add_derived()` |
| `filter(...)` | keep rows where the condition is True | `filter_active()` |

In `with_columns`, an expression whose output has the name of an existing column replaces that column. That's how `clean()` turns the text timestamps into datetimes under the same names.

## The building blocks used

```python
pl.col("created_at", "updated_at", "pushed_at")   # several columns, same operation
    .str.to_datetime(time_zone="UTC")             # .str namespace: text functions

pl.col("language").fill_null("Unknown")           # replace missing values

pl.lit(as_of)                                     # a Python value as an expression
(pl.lit(as_of) - pl.col("pushed_at")).dt.total_days().alias("days_since_last_push")

pl.when(pl.col("forks_count") > 0)                # if/else evaluated for every row
  .then(pl.col("stargazers_count") / pl.col("forks_count"))
  .otherwise(None)
  .alias("star_fork_ratio")
```

- `.alias()` names the result.
- `.str` and `.dt` are **namespaces**: groups of functions for text and for dates.
- Subtracting two datetimes gives a `Duration`; `.dt.total_days()` turns it into whole days.

## Boolean conditions (`filter_active`)

```python
df.filter(
    ~pl.col("archived")
    & ~pl.col("disabled")
    & (pl.col("days_since_last_push") <= max_days_since_push)
)
```

- Use `~` for NOT, `&` for AND and `|` for OR. Python's `not`, `and` and `or` don't work on columns.
- **The parentheses around the comparison are required.** In Python, `&` binds tighter than `<=`, so without them the line means `(~a & ~b & c) <= 365`. That's wrong, and sometimes it doesn't even raise an error.
- `filter` keeps a row only when the condition is `True`. A `null` result drops the row too. A repo that was never pushed has a null `days_since_last_push`, so it disappears as "inactive". That's intended here, but it's an easy way to lose rows by accident.

## Read more

- https://docs.pola.rs/user-guide/concepts/expressions-and-contexts/
- https://docs.pola.rs/api/python/stable/reference/expressions/index.html
