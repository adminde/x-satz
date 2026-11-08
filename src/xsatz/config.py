"""Settings file for the command line (ADR 0003).

The command line reads ``x-satz.conf``, written in TOML, from the directory it is started
in. The API never reads files on its own, it takes every value as an argument (ADR 0005).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from xsatz.sounds import STICKS, AudioSettings, CountIn, PartSound, Sound

SETTINGS_FILE = "x-satz.conf"
# Sections and keys the settings file may hold. Anything else is most likely a typo, which
# would otherwise be ignored without a word.
KEYS = {
    "theme": {"logo", "color"},
    "audio": {"softer", "reverb", "count_in", "transpose", "sounds", "soundfont_dir"},
}
COUNT_IN_KEYS = {"key", "dynamic"}
SOUND_KEYS = {"soundfont", "bank", "program", "swell", "fade_in"}
DYNAMICS = {"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"}


@dataclass
class Settings:
    logo: Path | None = None
    color: str | None = None
    audio: AudioSettings = field(default_factory=AudioSettings)


def read_settings(path: str | Path) -> Settings:
    """The settings in ``path``, or empty settings when the file does not exist.

    A relative logo path counts from the folder of the file, so the file works no matter
    where ``xsatz`` is started. Raises ValueError for a file that is no valid TOML or holds
    unknown sections, keys or values.
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
    try:
        audio = _audio(data.get("audio", {}), path.parent)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: [audio] {exc}") from exc
    return Settings(
        logo=path.parent / logo if logo else None,
        color=color or None,
        audio=audio,
    )


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a number")
    return float(value)


def _integer(value: object, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be a whole number from {low} to {high}")
    return value


def _table(value: object, name: str, keys: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a table")
    unknown = set(value) - keys if keys is not None else set()
    if unknown:
        raise ValueError(f"unknown key {sorted(unknown)[0]!r} in {name}")
    return value


def _audio(data: dict, folder: Path) -> AudioSettings:
    """The audio settings. A relative SoundFont folder counts from ``folder``."""
    settings = AudioSettings()
    if "softer" in data:
        settings.softer = _number(data["softer"], "softer")
    if "reverb" in data:
        settings.reverb = _number(data["reverb"], "reverb")
        if not 0 <= settings.reverb <= 1:
            raise ValueError("reverb must be from 0 to 1")
    if "count_in" in data:
        count_in = _table(data["count_in"], "count_in", COUNT_IN_KEYS)
        dynamic = count_in.get("dynamic", "f")
        if dynamic not in DYNAMICS:
            raise ValueError(f"count_in.dynamic must be one of {', '.join(sorted(DYNAMICS))}")
        key = _integer(count_in.get("key", STICKS), "count_in.key", 0, 127)
        settings.count_in = CountIn(key, dynamic)
    _transpose(_table(data.get("transpose", {}), "transpose"), "", settings.transpose)
    sounds = dict(_table(data.get("sounds", {}), "sounds"))
    for name, value in _table(sounds.pop("parts", {}), "sounds.parts").items():
        entry = _table(value, f"sounds.parts.{name}", SOUND_KEYS)
        settings.parts[name] = PartSound(**_sound_values(entry, f"sounds.parts.{name}"))
    _sounds(sounds, "", {}, settings.sounds)
    if "soundfont_dir" in data:
        if not isinstance(data["soundfont_dir"], str) or not data["soundfont_dir"].strip():
            raise ValueError("soundfont_dir must be a folder")
        settings.soundfont_dir = folder / Path(data["soundfont_dir"].strip()).expanduser()
    return settings


def _sound_values(entry: dict, name: str) -> dict:
    """The checked sound keys of ``entry``, only those it holds."""
    values = {}
    if "soundfont" in entry:
        soundfont = entry["soundfont"]
        if not isinstance(soundfont, str) or not soundfont.strip():
            raise ValueError(f"{name}.soundfont must be a name")
        values["soundfont"] = soundfont.strip()
    if "bank" in entry:
        values["bank"] = _integer(entry["bank"], f"{name}.bank", 0, 128)
    if "program" in entry:
        values["program"] = _integer(entry["program"], f"{name}.program", 0, 127)
    if "swell" in entry:
        values["swell"] = _number(entry["swell"], f"{name}.swell")
        if not 0 < values["swell"] < 1:
            raise ValueError(f"{name}.swell must lie between 0 and 1")
    if "fade_in" in entry:
        values["fade_in"] = _number(entry["fade_in"], f"{name}.fade_in")
        if not 0 <= values["fade_in"] <= 10:
            raise ValueError(f"{name}.fade_in must be from 0 to 10 seconds")
    return values


def _join(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key


def _transpose(table: dict, prefix: str, out: dict[str, int]) -> None:
    """Semitones by instrument sound, from nested tables such as [audio.transpose.brass]."""
    for key, value in table.items():
        sound = _join(prefix, key)
        if isinstance(value, dict):
            _transpose(value, sound, out)
        else:
            out[sound] = _integer(value, f"transpose.{sound}", -48, 48)


def _sounds(table: dict, prefix: str, inherited: dict, out: dict[str, Sound]) -> None:
    """Sounds by instrument sound, from nested tables such as [audio.sounds.brass].

    A table passes soundfont, bank, swell and fade_in on to the tables inside it, so that a
    family names them once. A table without a program that holds tables of its own is no
    sound itself, because a SoundFont without General MIDI programs could choose silence.
    """
    own = _sound_values({key: table[key] for key in SOUND_KEYS if key in table}, f"sounds.{prefix}")
    inner = any(isinstance(value, dict) for value in table.values())
    if own and prefix and ("program" in own or not inner):
        merged = inherited | own
        if "soundfont" not in merged:
            raise ValueError(f"sounds.{prefix} needs a soundfont")
        out[prefix] = Sound(**merged)
    passed = inherited | {key: value for key, value in own.items() if key != "program"}
    for key, value in table.items():
        if key in SOUND_KEYS:
            continue
        if not isinstance(value, dict):
            raise ValueError(f"unknown key {_join(prefix, key)!r} in sounds")
        _sounds(value, _join(prefix, key), passed, out)
