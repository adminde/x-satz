"""Settings file for the command line (ADR 0003).

The command line reads ``x-satz.conf``, written in TOML, from the directory it is started
in. The API never reads files on its own, it takes every value as an argument (ADR 0005).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

SETTINGS_FILE = "x-satz.conf"
# Sections and keys the settings file may hold. Anything else is most likely a typo, which
# would otherwise be ignored without a word.
KEYS = {"theme": {"logo", "color"}}


@dataclass
class Settings:
    logo: Path | None = None
    color: str | None = None


def read_settings(path: str | Path) -> Settings:
    """The settings in ``path``, or empty settings when the file does not exist.

    A relative logo path counts from the folder of the file, so the file works no matter
    where ``xsatz`` is started. Raises ValueError for a file that is no valid TOML or holds
    unknown sections or keys.
    """
    path = Path(path)
    if not path.is_file():
        return Settings()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    for section, values in data.items():
        if section not in KEYS or not isinstance(values, dict):
            raise ValueError(f"{path}: unknown section [{section}]")
        for key in values:
            if key not in KEYS[section]:
                raise ValueError(f"{path}: unknown key {key!r} in [{section}]")
    theme = data.get("theme", {})
    logo = str(theme.get("logo", "")).strip()
    color = str(theme.get("color", "")).strip()
    return Settings(
        logo=path.parent / logo if logo else None,
        color=color or None,
    )
