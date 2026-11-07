# 0007. A change is done when the gate is green

Date: 2026-11-07

## Status

Accepted

## Context

The checks of X-Satz live in several places: pre-commit for files and Ruff, pytest for the
code, and MuseScore for the actual engraving. A CI on GitHub cannot run MuseScore without
installing it, so a check that only exists in the CI either leaves the engraving out or
claims to cover it. Agents and people need one command that tells them whether a change is
done, and they need to see which part was not checked.

Other repositories of the maintainer use a single local gate with the exit codes 0 for
green, 1 for red and 2 for an environment error, and a stage that cannot run counts as
"not checked", never as green. X-Satz is public, so a CI on GitHub costs nothing and shows
contributors the state of a pull request.

## Decision

We will have one gate, `python tools/gates/verify.py`, with the stages

1. `pre-commit`: `pre-commit run --all-files` is green and leaves no untracked file behind,
2. `pytest`: the test suite passes,
3. `render`: the public domain fixture renders with MuseScore into a PDF with at least one
   page. Without MuseScore the stage is "not checked".

The gate exits with 0 for green, 1 for red and 2 for an environment error. A stage that is
"not checked" never counts as green: the last line of the gate names it, and `--strict`
turns it into red. The result of every stage goes to `tools/gates/last-run.json`, which is
git-ignored.

We will run the gate on every push through the `pre-push` hook, and the GitHub Actions CI
runs the same gate on Linux and Windows. The CI adds no checks of its own.

We will bring changes into `main` only through a pull request from a branch
`feature/<name>`, `fix/<name>` or `chore/<name>`, merged as a merge commit while the gate of
its newest commit is green. Nobody commits to `main` directly. Every report of finished work
states the result of each stage, including the stages that were not checked.

## Consequences

One command decides whether a change is done, the same way on every machine and in the CI.
Engraving is checked wherever MuseScore is installed, and where it is not, the gate says so
instead of passing silently.

The push hook takes longer than a plain test run, because it runs pre-commit on all files
and starts MuseScore once. Untracked files block a push until they are committed or ignored.

Changing a check means changing `.pre-commit-config.yaml`, the tests or
`tools/gates/verify.py`. A new rule that a check enforces needs a record. The CI stays
without MuseScore for now. Installing it there would turn the render stage green in the CI
as well.
