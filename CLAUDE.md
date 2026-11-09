# CLAUDE.md

Instructions for Claude Code when working in this repository.

## Project

Automated pipeline and analysis of Belgian electricity imbalance prices (Elia Open Data, dataset `ods134`).
Stack: Python, PostgreSQL (Neon), GitHub Actions, Power BI.
Everything in the repository is written in English: code, comments, docstrings, SQL, documentation.

## Structure

* `src/extract.py`: Elia API calls (`fetch_day`, `fetch_range`), with retries
* `src/db.py`: database connection, SQL file runner, upsert, quality test runner
* `src/pipeline.py`: entry point (`python src/pipeline.py daily|history`)
* `sql/`: setup files (tables and views), run in name order (`01_`, `02_`, ...)
* `tests/sql/`: data quality tests, one SELECT per file, returning the rows that fail
* `.github/workflows/daily.yml`: daily scheduled run

## Commands

* Build and check the database: `python src/db.py`
* Daily load (last 50 days) and quality tests: `python src/pipeline.py daily`
* Full history load: `python src/pipeline.py history` (slow, about 900 API calls: do not run unless asked)

## Code style: keep it simple

The code must stay readable by a junior data analyst. Match the existing style of the repository.

* Prefer explicit `for` / `while` loops and `if` / `else` over list comprehensions, `lambda`, `next()`, `map()` or `filter()`, unless the simple version is clearly worse.
* One function, one responsibility. Small functions, separate steps.
* No classes, decorators, type hints or design patterns unless explicitly asked.
* No new library without asking first. Built-in modules are preferred.
* Constants in CAPITAL LETTERS at the top of the file, after the imports.
* Imports in two groups: standard library first, then installed libraries, alphabetical order.
* Use `logging` (`logger = logging.getLogger(__name__)`), never `print`, except for the command-line usage message.
* Catch only the errors you can handle. Never use a bare `except:`.
* Two blank lines between functions. Only one `if __name__ == "__main__":` block, at the end of the files that are meant to be run.

## Comments and docstrings: professional, not educational

* Comments explain **why**, not what. Do not paraphrase the code.
* No tutorial tone: no "here we...", "this line...", "note that...", no explanations of basic Python or SQL.
* Keep them short. Remove a comment rather than keep an obvious one.
* Every function has a docstring with a one-line summary, then `Args`, `Returns` (with the exact type and content) and `Raises` when relevant.
* SQL files start with a short header: purpose, source, and whether the file can be run several times.

## SQL conventions

* Columns in `snake_case`, with the unit at the end when relevant (`_mw`, `_mwh`, `_eur_mwh`).
* Setup files must be safe to run several times (`IF NOT EXISTS`, `CREATE OR REPLACE VIEW`).
* Layers: `raw` (exact copy of the API, never modified), `clean` (renamed, harmonised, Belgian local time, business columns), `analytics` (one view per analysis question).
* Timestamps are stored in UTC (`TIMESTAMPTZ`). Analysis by day, month or hour uses Belgian local time (`clean.*_local` columns).
* Quality tests return the failing rows: 0 rows means the test passed. Known, documented exceptions are listed explicitly in the test.

## Working rules

* Work on the current feature branch. Never commit to `main`.
* Do one task at a time, and only change the files that task needs.
* Do not commit or push: the owner reviews `git diff` and commits himself.
* Run `python src/db.py` after any change to `sql/` or `tests/sql/`, and report the result.
* Never read, print or modify `.env`, and never write a connection string in any file.
