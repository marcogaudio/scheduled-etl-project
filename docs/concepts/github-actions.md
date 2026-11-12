# GitHub Actions, YAML and cron

GitHub Actions runs commands on GitHub's machines when something happens in the repository: a push, a pull request, a schedule, a button click.
- **CI** (continuous integration): testing every change automatically.
- **CD** (continuous delivery): shipping, or here running, the tested code automatically.

## Vocabulary

| Term | Meaning |
|---|---|
| workflow | a YAML file in `.github/workflows/` |
| event | what starts it (`on:`): `push`, `pull_request`, `schedule`, `workflow_dispatch` |
| job | a group of steps that runs on one machine |
| runner | that machine: a **fresh** Ubuntu VM for every run, deleted afterwards |
| step | one shell command (`run:`) or a reusable action (`uses:`) |
| action | a published, reusable step, e.g. `actions/checkout@v4` downloads the repo |
| expression | `${{ ... }}`, a value GitHub computes, e.g. `${{ secrets.GITHUB_TOKEN }}` |

## The two workflows

**`ci.yaml`** runs on every push and pull request: checkout, set up Python 3.12, `pip install -r requirements.txt`, `pytest -v`.

**`schedule.yaml`** runs the ETL every day:
1. checkout, Python, install, `pytest -q`. Broken code stops here, before touching data.
2. `actions/cache/restore` brings back yesterday's `data/output.duckdb`.
3. `python -m src.main --engine dlt`, with the token in the environment.
4. `actions/cache/save` stores today's database.
5. `actions/upload-artifact` makes the database and raw JSON downloadable for 30 days.
6. A small Python script writes a table of recent snapshot counts to `$GITHUB_STEP_SUMMARY`, shown on the run page. `continue-on-error: true`, so a problem there can't fail a good run.

## Keeping data between runs: cache vs artifact

The runner starts empty every time, so without help each day's database would contain only that day.

- **Cache**: for passing files *between runs*. `restore` asks for the key `duckdb-<run id>-<attempt>`, which never exists, then falls back to `restore-keys: duckdb-`, the newest cache whose key starts with that prefix: yesterday's database. Caches unused for 7 days are deleted; a daily job keeps it alive.
- **Artifact**: for *people* to download from the run page. Also a backup if the cache is ever lost.

## Secrets, variables, permissions

- `secrets.GITHUB_TOKEN` is created automatically for every run and expires when the run ends. Its API limit is 1,000 requests/hour per repository.
- **Repository variables** (Settings → Secrets and variables → Actions → Variables) hold non-secret values. `vars.GITHUB_ETL_REPOS` changes the tracked repos without a commit. If the variable isn't set it arrives as `""`, which `src/config.py` treats as unset.
- `permissions: contents: read` gives the run's token only the access it needs (least privilege).
- `concurrency: group: daily-etl` prevents two runs at once, which would write competing databases.
- `timeout-minutes: 15` kills a stuck run.
- `workflow_dispatch` inputs add a form to the "Run workflow" button. `${{ inputs.dry_run && '--dry-run' || '' }}` is the expression-language version of if/else.

## YAML in brief

- Indentation is the structure. Use spaces, never tabs.
- `key: value`, and lists with `- item`.
- `|` starts a multi-line block of text.
- Quote anything that starts with `*`, `{`, `[` or `#`. `"17 6 * * *"` needs quotes because a bare `*` means something else in YAML.

## Cron

`cron: "17 6 * * *"` has five fields: minute, hour, day of month, month, day of week. So: 06:17 every day.
- Always **UTC**.
- Minute 17 rather than 0, because the top of the hour is GitHub's busiest moment and runs there can be delayed.
- Other examples: `0 */6 * * *` is every 6 hours; `30 7 * * 1-5` is 07:30 on weekdays. https://crontab.guru explains any expression.

## Rules that surprise people

- Scheduled workflows run only from the **default branch**.
- In public repositories, schedules are disabled after **60 days without repository activity**.
- A failed scheduled run e-mails the person who last changed the `cron` line.
- A step that exits with a non-zero code fails the job, and the following steps are skipped. See [exit codes](exit-codes.md).

## Read more

- https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions
- https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/caching-dependencies-to-speed-up-workflows
