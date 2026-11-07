"""Configuration from a .env file for the command line (ADR 0003).

The command line reads a .env file from the directory it is started in, as most tools do.
The API never reads files on its own, it takes every value as an argument.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path


def read_env_file(path: str | Path) -> dict[str, str]:
    """Pairs of a .env file: KEY=VALUE per line, comments start with #.

    A value may be quoted. Without quotes, a # starts a comment only after a space, so a
    colour such as #711611 stays a value.
    """
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        key = key.removeprefix("export ").strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) > 1:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if key:
            values[key] = value
    return values


def load_env_file(path: str | Path, environ: MutableMapping[str, str]) -> list[str]:
    """Copy the pairs of ``path`` into ``environ`` where a key is not set yet.

    Variables already set in the environment win. Returns the keys taken from the file.
    """
    path = Path(path)
    if not path.is_file():
        return []
    taken = []
    for key, value in read_env_file(path).items():
        if key not in environ:
            environ[key] = value
            taken.append(key)
    return taken
