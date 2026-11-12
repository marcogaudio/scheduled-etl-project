# Virtual environments and dependencies

A virtual environment is a folder (here `.venv/`) with its own set of installed packages. Activating it puts its `bin/` folder first on your `PATH`, so `python` and `pip` refer to it and not to the system Python. Each project gets the library versions it needs without clashing with other projects.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
which python                       # should point inside .venv/
deactivate                         # leave the environment
```

`.venv/` is in `.gitignore`. You commit `requirements.txt`, never the environment itself.

## Pinning versions

`polars==1.36.1` pins an exact version, so every install (your laptop, the CI runner) gets the same code. Without pins, a new release of any library can break the daily job overnight while nothing changed in the repo. Ranges exist too: `>=1.30` is "at least", `~=1.36.0` is "1.36.x".

`dlt[duckdb]==1.28.0` uses an **extra**: the part in brackets installs the optional dependencies dlt needs for its DuckDB destination.

## This repo's requirements.txt

The file is the output of `pip freeze`. It pins both:
- the packages the code imports (polars, duckdb, dlt, requests, pytest, …)
- everything those pull in, the **transitive** dependencies (pendulum, sqlglot, tenacity, …)

That makes installs fully reproducible, but you can no longer tell from the file which packages the code really uses. Bigger projects often keep two files: a short `requirements.in` with the direct dependencies, and a pinned `requirements.txt` generated from it by pip-tools or uv.

To upgrade a library: change its pin, reinstall, run `pytest`, commit.

## Gotchas

- `pip install` without an active environment installs into the global Python.
- `python -m pip` always uses the pip that belongs to the `python` you're running. A bare `pip` might belong to a different interpreter.
- After pulling changes that touch `requirements.txt`, reinstall. Otherwise the tests run against old versions.

## Read more

- https://docs.python.org/3/library/venv.html
- https://pip.pypa.io/en/stable/reference/requirements-file-format/
