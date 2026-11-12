# ETL

ETL stands for **extract, transform, load**: copy data out of a source system, reshape it, and write it somewhere it can be analysed.

## The three steps here

| Step | Question it answers | Code |
|---|---|---|
| Extract | How do I get the data out? | `src/extract.py` or `extract_with_dlt()` call the GitHub API |
| Transform | How do I make it usable? | `src/transform.py`: pick fields, fix types, add columns, filter |
| Load | Where does it live? | `src/load.py` or `load_with_dlt()` write to DuckDB |

Each step is its own module and only talks to its neighbours through plain data: a list of dicts from extract to transform, a DataFrame from transform to load. That separation is what made it possible to swap in dlt for extract and load without touching the transform. `src/main.py` only calls the three in order.

## ETL vs ELT

In **ELT** the raw data is loaded first and transformed later, inside the database, usually with SQL (dbt is the common tool). Cloud warehouses made this popular because storage is cheap and SQL scales well.

This project is ETL: Polars transforms the data in Python before DuckDB sees it. It does keep the untouched API response in `data/raw/`, which gives one of ELT's advantages: you can re-run the transform on old data without calling the API again (`python -m src.transform`).

## Batch vs streaming

The pipeline runs once a day and processes everything in one go: a **batch** job. A **streaming** pipeline processes events continuously as they arrive (with tools like Kafka or Flink). Star counts change slowly and nobody needs them by the second, so batch is the natural choice.

## What makes a pipeline trustworthy

- **Idempotent**: running it twice gives the same result as running it once. See [idempotency](idempotency.md).
- **Fails loudly**: an error ends the run with a non-zero exit code rather than loading half the data. See [exit codes](exit-codes.md).
- **Observable**: the logs say what ran, how many rows, how long. See [logging](logging.md).
- **Reproducible**: pinned dependencies and explicit schemas, so tomorrow's run behaves like today's.
- **Testable**: every step runs on small, fixed inputs. See [pytest](pytest.md).

## Read more

- https://en.wikipedia.org/wiki/Extract,_transform,_load
- Martin Kleppmann, *Designing Data-Intensive Applications*, chapter 10 (batch processing)
