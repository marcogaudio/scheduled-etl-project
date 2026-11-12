# Environment variables and secrets

Every running program has a set of **environment variables**: `KEY=value` text pairs it inherits from whatever started it (your shell, GitHub Actions). In Python they're in `os.environ`.

```bash
export GITHUB_TOKEN=github_pat_...                  # for this shell session
GITHUB_ETL_LOAD_MODE=overwrite python -m src.main   # for one command only
```

## Why secrets go there

`config/config.toml` is committed, so anyone who can see the repo can read it. The GitHub token never goes there. It is read only from `GITHUB_TOKEN`:
- On your machine, it comes from `.env`.
- In GitHub Actions, the workflow injects `secrets.GITHUB_TOKEN`.

Same code, different environments, and the secret never touches git. This is the "config in the environment" rule of the twelve-factor app.

## .env and python-dotenv

`.env` is a plain file of `KEY=value` lines at the project root, listed in `.gitignore`. `load_settings()` calls `load_dotenv(PROJECT_ROOT / ".env")`, which copies those lines into `os.environ`.
- It **does not overwrite** variables that are already set, so a real environment variable always beats the file.
- If `.env` doesn't exist, it silently does nothing.

## In this repo (`src/config.py`)

- `_env_str()` strips the value and treats an empty string as "not set". This matters in GitHub Actions: `${{ vars.GITHUB_ETL_REPOS }}` becomes `""` when the variable isn't defined, and that must not wipe the repo list.
- `_env_list()` splits `"a/b, c/d"` into `("a/b", "c/d")`. Environment variables are always text, so lists are written comma-separated.
- `_env_int()` converts to `int` and raises a clear `ValueError` for something like `"abc"`.
- `Settings.github_token` uses `repr=False`, so printing the settings never shows the token.

## Gotchas

- Values are always strings. `"0"` and `"false"` are non-empty strings, so they're truthy in Python.
- A process reads its environment when it starts. Editing `.env` affects the next run, not one already running.
- `git check-ignore -v .env` confirms the file is ignored.
- If a token ever gets committed, revoke it on GitHub. Deleting the commit isn't enough: it stays in the history and in any clone.

## Read more

- https://12factor.net/config
- https://pypi.org/project/python-dotenv/
- https://docs.python.org/3/library/os.html#os.environ
