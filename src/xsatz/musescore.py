"""Find MuseScore and run it headless."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import cache
from pathlib import Path

# Common program names and default install locations of MuseScore 4
CANDIDATES = [
    "mscore4portable",
    "mscore4",
    "MuseScore4",
    "mscore",
    "musescore",
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
]


class MuseScoreNotFound(RuntimeError):
    pass


@cache
def executable() -> str:
    """Path to MuseScore; the environment variable MSCORE takes precedence."""
    if env := os.environ.get("MSCORE"):
        return env
    for cand in CANDIDATES:
        if found := shutil.which(cand) or (cand if Path(cand).exists() else None):
            return found
    raise MuseScoreNotFound(
        "MuseScore not found - set its path in the environment variable MSCORE."
    )


def run(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if sys.platform.startswith("linux"):
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run(
        [executable(), *args], env=env, capture_output=True, text=True, timeout=timeout
    )


def version() -> str:
    res = run(["--version"], timeout=60)
    out = (res.stdout or res.stderr).strip()
    return out.splitlines()[-1] if out else "?"
