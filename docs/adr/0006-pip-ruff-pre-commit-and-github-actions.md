# 0006. pip, Ruff, pre-commit and GitHub Actions

Date: 2026-11-07

## Status

Accepted

## Context

The core is developed on Windows and is meant to run on Linux as well. Contributors and agents
set up the environment anew, so the setup should rely on tools that every Python installation
brings along and that most Python developers know.

`venv` and `pip` ship with Python and install a project with optional extras straight from
`pyproject.toml`. Newer managers such as uv, Poetry or PDM add lock files and speed, but are one
more tool to install and learn. Without a lock file, every installation gets the newest versions
that satisfy the lower bounds in `pyproject.toml`, so results can change with a new release of a
dependency.

Ruff replaces Flake8, isort and Black with one tool. pytest is the standard test runner.

Checks should run before code leaves the machine, not only in the CI after a push. pre-commit
runs hooks on `git commit` and `git push` and manages the environments of most hooks itself.

## Decision

We will:

- set up the environment with `python -m venv` and `pip install -e ".[dev]"`, declare runtime
  dependencies with lower bounds in `pyproject.toml` and development tools in the `dev` extra,
  and keep no lock file for now.
- use Ruff (`ruff check`, `ruff format`) as the only linter and formatter, configured in
  `pyproject.toml`.
- use pytest for all tests.
- use pre-commit (`.pre-commit-config.yaml`) with
  - the checks for copyrighted scores and for `.env` files
    ([ADR 0003](0003-public-repository-without-protected-or-personal-data.md)),
  - the generic hooks of `pre-commit/pre-commit-hooks` (whitespace, end of file, YAML/TOML,
    merge conflicts, large files, case conflicts, line endings),
  - Ruff through the official `astral-sh/ruff-pre-commit` hooks, with the same Ruff version
    pinned in the `dev` extra so that editors and hooks agree,
  - the gate ([ADR 0007](0007-a-change-is-done-when-the-gate-is-green.md)) on `pre-push`,
    run in the activated virtual environment.
- run a GitHub Actions CI (`.github/workflows/ci.yml`) on every push and pull request that runs
  the gate on Linux (Python 3.11 and 3.13) and Windows (Python 3.13).
- pin actions to full commit SHAs with a version comment and let Dependabot update the actions,
  the pre-commit hooks and the pins in `pyproject.toml`.

## Consequences

Setting up needs nothing beyond Python and git. The same hooks run locally and in the CI from
one definition.

Without a lock file, the CI always tests against the newest dependency releases. Breaking
releases show up early, but two machines may install different versions. If that becomes a
problem, a constraints file or a lock file can be added without changing the rest of this
decision.

The Ruff version is pinned in two places, `pyproject.toml` and `.pre-commit-config.yaml`, and has
to be raised in both. The push hook only works inside the activated virtual environment,
because the gate needs the project's dependencies. pre-commit has to be installed once per clone
(`pre-commit install`). Hooks can be skipped with `--no-verify`, which the CI catches.

The CI has no MuseScore, so render tests only run locally (see
[ADR 0008](0008-musescore-4-and-the-stages-around-it.md)).
