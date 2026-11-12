# Polars DataFrames, eager and lazy

Polars is a DataFrame library written in Rust. A **DataFrame** is a table. Each column is a **Series** with exactly one data type, and the data is stored column by column in memory using the [Apache Arrow](apache-arrow.md) layout. That layout, plus running work in parallel on all CPU cores, is why it's fast.

```python
df = pl.DataFrame(rows, schema=RAW_SCHEMA)   # transform.to_frame()
df.height      # number of rows
df.schema      # column names and types
df.head(5)     # first rows
```

## DataFrames never change in place

Every operation returns a **new** DataFrame, so you either reassign (`df = df.filter(...)`) or chain calls. `transform()` chains the steps with `.pipe()`:

```python
df = (
    to_frame(raw)
    .pipe(clean)                         # clean(df)
    .pipe(add_derived, as_of)            # add_derived(df, as_of)
    .pipe(filter_active, max_days_since_push)
    .select(OUTPUT_COLUMNS)
)
```

`df.pipe(f, x)` is just `f(df, x)`. The chain reads top to bottom like a recipe, the same as `|>` in R. Because nothing is modified in place, the test `test_transform_does_not_modify_its_input` can check that the raw input is identical after the call.

## Coming from R / dplyr

| dplyr | Polars |
|---|---|
| `select(df, a, b)` | `df.select("a", "b")` |
| `mutate(df, c = a / b)` | `df.with_columns((pl.col("a") / pl.col("b")).alias("c"))` |
| `filter(df, a > 1)` | `df.filter(pl.col("a") > 1)` |
| `if_else(cond, x, y)` | `pl.when(cond).then(x).otherwise(y)` |
| `replace_na(x, "NONE")` | `pl.col("x").fill_null("NONE")` |
| `group_by(g) \|> summarise(n = n())` | `df.group_by("g").agg(pl.len())` |
| `df \|> f()` | `df.pipe(f)` |
| `NA` | `null` (`None` in Python) |

## Eager vs lazy

What this repo uses is **eager**: each method runs immediately. Polars also has a **lazy** API:

```python
plan = df.lazy().filter(pl.col("archived").not_()).select("full_name")
print(plan.explain())   # the optimised query plan
result = plan.collect() # only now does any work happen
```

With the whole plan known in advance, Polars can optimise it:
- **predicate pushdown**: apply filters as early as possible, ideally while reading the file
- **projection pushdown**: read only the columns that are used
- remove redundant steps

`pl.scan_parquet()` and `pl.scan_csv()` start a lazy query straight from a file.

For a few dozen repositories the difference is invisible, so the code stays eager. With millions of rows or large files, lazy is the default choice. The transform functions only use `with_columns`, `filter` and `select`, which exist on both `DataFrame` and `LazyFrame`, so switching would be easy.

## Read more

- https://docs.pola.rs/user-guide/
- https://docs.pola.rs/user-guide/lazy/
