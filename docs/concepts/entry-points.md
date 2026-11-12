# Modules, packages and entry points

## Modules and packages

A **module** is one `.py` file. A **package** is a folder of modules, marked as a regular package by an `__init__.py` file. `src/`, `dlt_pipeline/` and `tests/` each have one, so `from src.config import load_settings` means "the module `config` inside the package `src`".

## How Python finds an import

`import src` searches the folders listed in `sys.path`, in order, and stops at the first match. The first entry depends on how Python was started:

| Command (from the project root) | First entry of `sys.path` | `import src` works? |
|---|---|---|
| `python -m src.main` | the current folder: the project root | yes |
| `python src/main.py` | `src/` | no: Python looks for `src/src/` |
| `pytest` | the folder above the top package of each test file. `tests/` is a package, so that's the project root | yes |

Hence the rule: run everything from the project root with `python -m`. `ModuleNotFoundError: No module named 'src'` almost always means one of the two was broken.

## `if __name__ == "__main__":`

Python sets `__name__` to `"__main__"` in the file you started, and to the module's name (`"src.extract"`) when the file is imported. Code under this `if` runs only when you start the file directly.

Every step module uses it for a small demo:
- `python -m src.extract` downloads and saves the raw JSON.
- `python -m src.transform` transforms the newest raw file.

The tests import the same modules without running anything.

`src/main.py` is the real **entry point**. Its block calls `sys.exit(main())`, so the return value becomes the program's [exit code](exit-codes.md).

## Name shadowing

The current folder comes first on `sys.path`, so a local folder or file with the same name as an installed library hides the library. That's why the dlt code lives in `dlt_pipeline/` and not in `dlt/`: inside the project, `import dlt` would load our folder instead of the dlt library. A file named `polars.py` or `json.py` in the project root causes the same kind of confusing error.

## Read more

- https://docs.python.org/3/tutorial/modules.html
- https://docs.python.org/3/library/__main__.html
- https://docs.pytest.org/en/stable/explanation/pythonpath.html
