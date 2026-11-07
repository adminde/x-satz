#!/usr/bin/env python3
"""Gate of the repository, the one check before every push and merge (ADR 0007).

Exit 0 green, 1 red, 2 environment error.

Stages:
  pre-commit  pre-commit on all files. Afterwards no untracked file may be left over.
  pytest      the test suite.
  render      prepares and renders the public domain fixture with the score style through
              MuseScore and expects a PDF with at least one page. Without MuseScore the
              stage is "not checked".

A stage that cannot run because a part of the environment is missing is "not checked".
It never counts as green: the last line names it, and with --strict the gate is red.

Writes the result of every stage to tools/gates/last-run.json. Run it inside the
activated virtual environment, since the stages need the dependencies of the project.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "tools" / "gates" / "last-run.json"
FIXTURE = ROOT / "tests" / "fixtures" / "entchen.musicxml"

GREEN, RED, ENV, NOT_CHECKED = 0, 1, 2, 3
VERDICTS = {GREEN: "green", RED: "red", ENV: "environment error", NOT_CHECKED: "not checked"}


def has_module(name: str) -> bool:
    proc = subprocess.run([sys.executable, "-c", f"import {name}"], capture_output=True)
    return proc.returncode == 0


def stage_pre_commit() -> int:
    if not has_module("pre_commit"):
        print('pre-commit is not installed: python -m pip install -e ".[dev]"')
        return ENV
    proc = subprocess.run([sys.executable, "-m", "pre_commit", "run", "--all-files"], cwd=ROOT)
    if proc.returncode != 0:
        return RED
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    if untracked:
        print("Untracked files, add them to git or to .gitignore:")
        print("\n".join(untracked))
        return RED
    return GREEN


def stage_pytest() -> int:
    if not has_module("pytest"):
        print('pytest is not installed: python -m pip install -e ".[dev]"')
        return ENV
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    return GREEN if proc.returncode == 0 else RED


def stage_render() -> int:
    if not has_module("xsatz"):
        print('xsatz is not installed: python -m pip install -e ".[dev]"')
        return ENV
    from xsatz import musescore

    try:
        print(f"MuseScore: {musescore.executable()}")
    except musescore.MuseScoreNotFound as exc:
        print(exc)
        return NOT_CHECKED
    import pymupdf

    from xsatz.render import default_style, render

    with tempfile.TemporaryDirectory() as out:
        res = render(FIXTURE, out, style=default_style())
        if not res.ok:
            print(res.log)
            return RED
        with pymupdf.open(res.outputs[0]) as doc:
            print(f"{res.outputs[0].name}: {doc.page_count} page(s)")
            return GREEN if doc.page_count >= 1 else RED


STAGES: tuple[tuple[str, Callable[[], int]], ...] = (
    ("pre-commit", stage_pre_commit),
    ("pytest", stage_pytest),
    ("render", stage_render),
)


def overall(verdicts: list[str], strict: bool) -> int:
    """Combine the verdicts of the stages into the exit code of the gate."""
    if "red" in verdicts or (strict and "not checked" in verdicts):
        return RED
    if "environment error" in verdicts:
        return ENV
    return GREEN


def summary(results: list[dict[str, object]], code: int) -> str:
    """Last line of the gate, naming every stage that was not checked."""
    line = {GREEN: "GREEN", RED: "RED", ENV: "ENVIRONMENT ERROR"}[code]
    open_stages = [str(r["stage"]) for r in results if r["result"] == "not checked"]
    if open_stages:
        noun = "stage" if len(open_stages) == 1 else "stages"
        line += f" ({len(open_stages)} {noun} not checked: {', '.join(open_stages)})"
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate of X-Satz.")
    parser.add_argument(
        "--strict", action="store_true", help="a stage that is not checked makes the gate red"
    )
    strict = parser.parse_args(argv).strict
    results: list[dict[str, object]] = []
    for name, stage in STAGES:
        print(f"== {name}", flush=True)
        start = time.monotonic()
        verdict = VERDICTS.get(stage(), "red")
        seconds = round(time.monotonic() - start, 1)
        print(f"== {name}: {verdict} ({seconds} s)", flush=True)
        results.append({"stage": name, "result": verdict, "seconds": seconds})
    code = overall([str(r["result"]) for r in results], strict)
    report = {"result": VERDICTS[code], "strict": strict, "stages": results}
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(summary(results, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
