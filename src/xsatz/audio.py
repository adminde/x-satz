"""MusicXML -> MP3s and MIDIs for practising, through MuseScore (ADR 0010).

One MP3 of the whole band and one practice MP3 per part in which the other parts play
softer, on request also as MIDI. MuseScore imports the sounding copy of ``xsatz.sounds``.
The MP3s are exported from MuseScore's file with the sounds and volumes of
``xsatz.mscz.set_audio``. The practice MIDIs are copies of the MIDI with lower velocities in
the tracks of the other parts, because the MIDI export does not read the mixer.
"""

from __future__ import annotations

import array
import math
import shutil
import struct
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from pathlib import Path

from xsatz import musescore
from xsatz.mscz import AudioTrack, play_unisons_once, set_audio
from xsatz.parts import part_file_name
from xsatz.prepare import DOCTYPE, PrepareResult, prepare
from xsatz.soundfont import Shaping, shape
from xsatz.sounds import (
    COUNT_IN_ID,
    AudioSettings,
    Sound,
    SoundsResult,
    part_sounds,
    prepare_sounds,
)

# The bit rate of the director's MP3 exports from Dorico, in kbit/s.
BITRATE = "256"
# Highest level of the full mix in dB below full scale. MuseScore mixes the whole band of
# the reference piece up to 8 dB above full scale, and an MP3 clips there.
PEAK_DB = -1.0


@dataclass
class PracticeFile:
    name: str
    mp3: Path | None = None
    midi: Path | None = None


@dataclass
class AudioResult:
    source: Path
    full: Path | None
    full_midi: Path | None = None
    practice: list[PracticeFile] = field(default_factory=list)
    log: str = ""
    prepared: PrepareResult | None = None
    sounds: SoundsResult | None = None
    master_db: float = 0.0
    shaped: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.full is not None


def render_audio(
    source: str | Path,
    out_dir: str | Path | None = None,
    settings: AudioSettings | None = None,
    midi: bool = False,
) -> AudioResult:
    """Write ``<stem>.mp3`` and ``<stem> - <part>.mp3`` for every part of ``source``.

    With ``midi`` the same files are written as MIDI as well. In a practice file the other
    parts play ``settings.softer`` decibels softer, the count-in never. Without ``out_dir``
    the files are written next to ``source``.
    """
    source = Path(source)
    settings = settings or AudioSettings()
    out_dir = Path(out_dir) if out_dir is not None else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xsatz-") as work:
        work = Path(work)
        copy_path = work / f"{source.stem}.musicxml"
        prepared = prepare(source, copy_path)
        root = ET.parse(copy_path).getroot()
        changes = prepare_sounds(root, settings)
        body = ET.tostring(root, encoding="unicode")
        copy_path.write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n{body}\n', encoding="utf-8"
        )
        result = AudioResult(source, None, prepared=prepared, sounds=changes)
        score = work / f"{source.stem}.mscz"
        result.log += _run(["-o", str(score), str(copy_path)])
        if not score.exists():
            result.log = result.log[-2000:]
            return result
        staves = _staves(root)
        sounds = _shaped(part_sounds(root, settings), settings, result)
        count_in = {i for i, (part_id, _, _) in enumerate(staves) if part_id == COUNT_IN_ID}
        data = _midi(score, work, out_dir / f"{source.stem}.mid", staves, result) if midi else None
        result.master_db = _master(score, work, sounds, settings, count_in, result)
        target = out_dir / f"{source.stem}.mp3"
        result.full = _mp3(score, work, target, sounds, settings, None, count_in, result)
        first = 0
        for index, (part_id, name, count) in enumerate(staves):
            own = set(range(first, first + count))
            first += count
            if part_id == COUNT_IN_ID:
                continue
            target = out_dir / part_file_name(source.stem, name, "mp3")
            mp3 = _mp3(score, work, target, sounds, settings, index, count_in, result)
            practice = PracticeFile(name, mp3)
            if data is not None:
                quiet = set(range(track_count(data))) - own - _count_in_tracks(staves)
                practice.midi = out_dir / part_file_name(source.stem, name, "mid")
                practice.midi.write_bytes(
                    scale_velocities(data, quiet, 10 ** (-settings.softer / 40))
                )
            result.practice.append(practice)
    result.log = result.log[-2000:]
    return result


def _midi(
    score: Path, work: Path, target: Path, staves: list[tuple[str, str, int]], result: AudioResult
) -> bytes | None:
    """Export ``score`` as MIDI to ``target``. Returns its bytes when it has a track per staff."""
    midi = work / target.name
    result.log += _run(["-o", str(midi), str(score)])
    if not midi.exists():
        return None
    shutil.copyfile(midi, target)
    result.full_midi = target
    data = target.read_bytes()
    tracks = track_count(data)
    if tracks != sum(n for _, _, n in staves):
        result.log += f"\n{target.name}: {tracks} tracks for {len(staves)} parts, no practice MIDIs"
        return None
    return data


def _shaped(sounds: list[Sound | None], settings: AudioSettings, result: AudioResult) -> list:
    """The sounds with swell or fade-in replaced by sounds of shaped copies.

    A copy of ``<soundfont>.sf2`` in the SoundFont folder is written next to it, where
    MuseScore finds it as well, once for every shaping and again when the original is
    newer. Raises ValueError without a folder or the file of the SoundFont.
    """
    groups: dict[Shaping, list[int]] = {}
    for index, sound in enumerate(sounds):
        if sound is None or (sound.swell is None and sound.fade_in is None):
            continue
        if settings.soundfont_dir is None:
            raise ValueError("audio.soundfont_dir is needed to shape a SoundFont")
        file = settings.soundfont_dir / f"{sound.soundfont}.sf2"
        if not file.is_file():
            raise ValueError(f"{file}: no SF2 SoundFont to shape")
        groups.setdefault(Shaping(file, sound.swell, sound.fade_in), []).append(index)
    out = list(sounds)
    for shaping, used in groups.items():
        target = shaping.file.with_name(f"{shaping.name()}{shaping.file.suffix}")
        programs = {(sounds[i].bank, sounds[i].program) for i in used}
        presets = None if any(program is None for _, program in programs) else programs
        if not target.exists() or target.stat().st_mtime < shaping.file.stat().st_mtime:
            shape(shaping, target, presets)
        result.shaped.append(target)
        for i in used:
            out[i] = replace(sounds[i], soundfont=shaping.name(), swell=None, fade_in=None)
    return out


def _master(
    score: Path,
    work: Path,
    sounds: list[Sound | None],
    settings: AudioSettings,
    count_in: set[int],
    result: AudioResult,
) -> float:
    """The volume of the whole mix that keeps the full mix at ``PEAK_DB``, never above 0 dB.

    The full mix is rendered once as WAV to measure its peak. Every file of a piece gets the
    same volume, so that full mix and practice files keep their level against each other.
    """
    probe = _mix(score, work, work / "probe.wav", sounds, settings, None, count_in, 0.0, result)
    peak = wav_peak(probe) if probe is not None else 0.0
    if peak <= 0:
        return 0.0
    return min(0.0, PEAK_DB - 20 * math.log10(peak))


def wav_peak(path: Path) -> float:
    """The highest absolute sample of a WAV file of 16 bit or 32 bit float, 1.0 at full scale."""
    data = path.read_bytes()
    position, kind = 12, None
    while position + 8 <= len(data):
        chunk, size = (
            data[position : position + 4],
            struct.unpack("<I", data[position + 4 : position + 8])[0],
        )
        body = data[position + 8 : position + 8 + size]
        if chunk == b"fmt ":
            kind = struct.unpack("<H", body[:2])[0]
        elif chunk == b"data":
            if kind == 3:
                samples = array.array("f", body[: len(body) // 4 * 4])
                return max(max(samples, default=0.0), -min(samples, default=0.0))
            samples = array.array("h", body[: len(body) // 2 * 2])
            return max(max(samples, default=0), -min(samples, default=0)) / 32768
        position += 8 + size + (size & 1)
    return 0.0


def _mp3(
    score: Path,
    work: Path,
    target: Path,
    sounds: list[Sound | None],
    settings: AudioSettings,
    own: int | None,
    count_in: set[int],
    result: AudioResult,
) -> Path | None:
    """Export ``score`` as MP3 to ``target``, as practice file of the part ``own`` if given.

    In a practice file the other parts except the count-in play softer, and of every unison
    of parts with the same samples the own part sounds. MuseScore crashes when a conversion
    job holds MP3 exports, so every MP3 takes a run of its own.
    """
    return _mix(score, work, target, sounds, settings, own, count_in, result.master_db, result)


def _mix(
    score: Path,
    work: Path,
    target: Path,
    sounds: list[Sound | None],
    settings: AudioSettings,
    own: int | None,
    count_in: set[int],
    master_db: float,
    result: AudioResult,
) -> Path | None:
    mixed = work / f"mix-{target.stem}.mscz"
    shutil.copyfile(score, mixed)
    tracks = []
    for index, sound in enumerate(sounds):
        softer = own is not None and index != own and index not in count_in
        tracks.append(AudioTrack(sound, -settings.softer if softer else 0.0, settings.reverb))
    set_audio(mixed, tracks, master_db)
    play_unisons_once(mixed, own)
    bitrate = ["-b", BITRATE] if target.suffix == ".mp3" else []
    result.log += _run([*bitrate, "-o", str(target), str(mixed)])
    return target if target.exists() else None


def _run(args: list[str]) -> str:
    res = musescore.run(args)
    return res.stdout + res.stderr


def _staves(root: ET.Element) -> list[tuple[str, str, int]]:
    """Id, name and number of staves of every part, in the order MuseScore writes tracks."""
    parts = {part.get("id"): part for part in root.findall("part")}
    out = []
    for score_part in root.findall("part-list/score-part"):
        part_id = score_part.get("id", "")
        part = parts.get(part_id)
        staves = int(part.findtext("measure/attributes/staves") or 1) if part is not None else 1
        out.append((part_id, score_part.findtext("part-name") or part_id, staves))
    return out


def _count_in_tracks(staves: list[tuple[str, str, int]]) -> set[int]:
    first = 0
    for part_id, _, count in staves:
        if part_id == COUNT_IN_ID:
            return set(range(first, first + count))
        first += count
    return set()


def _chunks(data: bytes) -> list[tuple[bytes, int, int]]:
    """Type, start and end of the body of every chunk of a standard MIDI file."""
    if data[:4] != b"MThd":
        raise ValueError("not a standard MIDI file")
    chunks = []
    position = 0
    while position + 8 <= len(data):
        kind = data[position : position + 4]
        length = struct.unpack(">I", data[position + 4 : position + 8])[0]
        chunks.append((kind, position + 8, position + 8 + length))
        position += 8 + length
    return chunks


def track_count(data: bytes) -> int:
    return sum(1 for kind, _, _ in _chunks(data) if kind == b"MTrk")


def _number(data: bytes | bytearray, position: int) -> tuple[int, int]:
    """A variable length number and the position after it."""
    value = 0
    while True:
        byte = data[position]
        position += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, position


def scale_velocities(data: bytes, tracks: set[int], factor: float) -> bytes:
    """A copy of the MIDI file ``data`` with the note velocities of ``tracks`` scaled.

    General MIDI players turn velocity into loudness by its square, so a factor of
    10 ** (-dB / 40) makes a track dB decibels softer. MuseScore's own SoundFont follows
    velocity a little more steeply, there 15 dB become about 17 dB. Only velocity bytes
    change, so every event keeps its length and position.
    """
    out = bytearray(data)
    track = -1
    for kind, start, end in _chunks(data):
        if kind != b"MTrk":
            continue
        track += 1
        if track not in tracks:
            continue
        position, status = start, 0
        while position < end:
            _, position = _number(out, position)
            byte = out[position]
            if byte == 0xFF:
                length, position = _number(out, position + 2)
                position += length
                continue
            if byte in (0xF0, 0xF7):
                length, position = _number(out, position + 1)
                position += length
                continue
            if byte & 0x80:
                status = byte
                position += 1
            size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
            if status & 0xF0 == 0x90 and out[position + 1] > 0:
                out[position + 1] = max(1, round(out[position + 1] * factor))
            position += size
    return bytes(out)
