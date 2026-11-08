"""Turn a prepared copy of a MusicXML file into the copy MuseScore plays (ADR 0010).

The engraving copy of ADR 0008 prints what the players read. The sounding copy always puts
the percussion on General MIDI drum keys and marks the unisons of parts with the same
samples. Everything else is played as written, unless the audio settings transpose
instruments or ask for a count-in.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path

# General MIDI drum keys, counted from 0, by MusicXML instrument sound.
DRUM_KEYS = {
    "metal.cymbal.splash": 55,
    "metal.cymbal.chinese": 52,
    "metal.cymbal.crash": 49,
    "metal.cymbal.ride": 51,
    "metal.hi-hat": 42,
    "metal.bells.cowbell": 56,
    "drum.snare-drum": 38,
    "drum.timbale": 65,
    "drum.tambourine": 54,
    "drum.kick-drum": 36,
    "drum.bass-drum": 36,
}
# Noteheads that stand for another sound of the same instrument.
HEAD_KEYS = {
    ("metal.cymbal.ride", "circle-x"): 53,
    ("drum.snare-drum", "x"): 37,
}
OPEN_HI_HAT, PEDAL_HI_HAT = 46, 44
# High to low. Dorico gives every tom the same sound, so the name tells floor toms from
# rack toms and the staff position orders them.
RACK_TOMS, FLOOR_TOMS = (48, 45, 47, 50), (43, 41)
# An instrument without a sound, such as body percussion, claps.
HAND_CLAP = 39
# The count-in ticks with sticks at forte unless the settings say otherwise, chosen by ear
# from the short sounds of MS Basic. Dorico's count-in is as loud as the music. At forte the
# sticks of MS Basic peak at the level of the band, at fortississimo they clip.
STICKS = 31
# Diatonic steps of the semitones within an octave, for the transposition MusicXML wants.
DIATONIC = (0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6)
STEPS = "CDEFGAB"

COUNT_IN_ID = "XSATZ-COUNT-IN"
COUNT_IN_NAME = "Count-in"
TYPES = {
    Fraction(1, 2): "eighth",
    Fraction(1): "quarter",
    Fraction(2): "half",
    Fraction(4): "whole",
}


@dataclass(frozen=True)
class Sound:
    """A sound of a SoundFont that MuseScore knows by its file name without extension.

    Without a program the SoundFont chooses the sound itself, as General MIDI does. With
    ``swell`` or ``fade_in`` it plays from a shaped copy (``xsatz.soundfont.Shaping``).
    """

    soundfont: str
    bank: int = 0
    program: int | None = None
    swell: float | None = None
    fade_in: float | None = None


@dataclass(frozen=True)
class CountIn:
    key: int = STICKS
    dynamic: str = "f"


@dataclass(frozen=True)
class PartSound:
    """What a single part changes in the sound of its instrument. None keeps that value."""

    soundfont: str | None = None
    bank: int | None = None
    program: int | None = None
    swell: float | None = None
    fade_in: float | None = None


@dataclass
class AudioSettings:
    """How the audio files differ from the score. The defaults play the score as written.

    ``transpose`` and ``sounds`` are keyed by the start of the MusicXML instrument sound,
    the longest match wins. ``parts`` changes the sound of single parts by part name.
    ``soundfont_dir`` holds the SoundFonts to shape and their shaped copies. Without
    ``reverb`` MuseScore sends its own share. ``softer`` is how many decibels the other
    parts play softer in a practice file.
    """

    transpose: dict[str, int] = field(default_factory=dict)
    sounds: dict[str, Sound] = field(default_factory=dict)
    parts: dict[str, PartSound] = field(default_factory=dict)
    soundfont_dir: Path | None = None
    count_in: CountIn | None = None
    reverb: float | None = None
    softer: float = 15.0


# MuseScore's own SoundFont, which a part plays when nothing else is chosen.
MS_BASIC = "MS Basic"


def part_sounds(root: ET.Element, settings: AudioSettings) -> list[Sound | None]:
    """The sound of every part in the part order, None for MuseScore's own choice."""
    out = []
    for score_part, sound in zip(
        root.findall("part-list/score-part"), instrument_sounds(root), strict=True
    ):
        chosen = matching(settings.sounds, sound) if sound else None
        override = settings.parts.get(score_part.findtext("part-name") or "")
        if override is not None:
            base = chosen or Sound(MS_BASIC)
            changes = {
                name: getattr(override, name)
                for name in ("soundfont", "bank", "program", "swell", "fade_in")
                if getattr(override, name) is not None
            }
            chosen = replace(base, **changes)
        out.append(chosen)
    return out


def matching(table: dict, sound: str):
    """The value of the longest key of ``table`` that ``sound`` starts with, or None."""
    keys = [key for key in table if sound.startswith(key)]
    return table[max(keys, key=len)] if keys else None


def instrument_sounds(root: ET.Element) -> list[str]:
    """The instrument sound of the first instrument of every part, in the part order."""
    return [
        sp.findtext("score-instrument/instrument-sound") or ""
        for sp in root.findall("part-list/score-part")
    ]


@dataclass
class SoundsResult:
    transposed: list[str] = field(default_factory=list)
    drum_keys: int = 0
    open_hi_hats: int = 0
    unmapped: list[str] = field(default_factory=list)
    count_in_bars: int = 0
    count_in_clicks: int = 0
    unisons: int = 0


def _is_percussion(part: ET.Element) -> bool:
    return part.findtext("measure/attributes/clef/sign") == "percussion"


def _sounds(root: ET.Element) -> dict[str, str]:
    """The instrument sound of the first instrument of every part, by part id."""
    return {
        sp.get("id", ""): sp.findtext("score-instrument/instrument-sound") or ""
        for sp in root.findall("part-list/score-part")
    }


def _insert_transpose(attributes: ET.Element) -> ET.Element:
    """An empty transposition at its place in the attributes, after clefs and staff details."""
    transpose = ET.Element("transpose")
    ET.SubElement(transpose, "diatonic").text = "0"
    ET.SubElement(transpose, "chromatic").text = "0"
    later = [i for i, c in enumerate(attributes) if c.tag in ("directive", "measure-style")]
    attributes.insert(later[0] if later else len(attributes), transpose)
    return transpose


def _add(transpose: ET.Element, tag: str, value: int) -> None:
    element = transpose.find(tag)
    if element is None:
        element = ET.SubElement(transpose, tag)
        element.text = "0"
    element.text = str(int(element.text or 0) + value)


def _steps(semitones: int) -> tuple[int, int, int]:
    """Diatonic steps, chromatic steps and octaves of a transposition by ``semitones``."""
    octaves = int(semitones / 12)
    rest = semitones - 12 * octaves
    sign = -1 if rest < 0 else 1
    return sign * DIATONIC[abs(rest)], rest, octaves


def transpose_to_sounding(root: ET.Element, transpose: dict[str, int]) -> list[str]:
    """Add the semitones of ``transpose`` to the transposition of the pitched parts.

    A band whose brass read in C but play in B flat sounds a whole tone lower than Dorico
    exports, its sousaphone a ninth (ADR 0010). Returns the ids of the parts changed.
    """
    sounds = _sounds(root)
    changed = []
    for part in root.findall("part"):
        semitones = matching(transpose, sounds.get(part.get("id", ""), ""))
        if not semitones or _is_percussion(part):
            continue
        shift = _steps(semitones)
        elements = list(part.iter("transpose"))
        if not elements:
            attributes = part.find("measure/attributes")
            if attributes is None:
                continue
            elements = [_insert_transpose(attributes)]
        diatonic, chromatic, octaves = shift
        for element in elements:
            _add(element, "diatonic", diatonic)
            _add(element, "chromatic", chromatic)
            if octaves:
                _add(element, "octave-change", octaves)
        changed.append(part.get("id", ""))
    return changed


def _timeline(
    measure: ET.Element, divisions: int
) -> tuple[list[tuple[Fraction, ET.Element]], Fraction]:
    """Start of every note of a measure in quarters, and the length of the measure."""
    position = last = longest = Fraction(0)
    notes = []
    for child in measure:
        if child.tag not in ("note", "backup", "forward"):
            continue
        duration = Fraction(int(child.findtext("duration") or 0), divisions)
        if child.tag == "backup":
            position -= duration
            continue
        if child.tag == "forward":
            position += duration
        elif child.find("chord") is not None:
            notes.append((last, child))
        else:
            notes.append((position, child))
            last = position
            position += duration
        longest = max(longest, position)
    return notes, longest


def _divisions(measure: ET.Element, current: int) -> int:
    return int(measure.findtext("attributes/divisions") or current)


def _position(note: ET.Element) -> int:
    step = note.findtext("unpitched/display-step") or "B"
    octave = int(note.findtext("unpitched/display-octave") or 4)
    return octave * 7 + STEPS.index(step)


def _technical(note: ET.Element) -> set[str]:
    marks = set()
    for technical in note.iter("technical"):
        for mark in technical:
            marks.add(mark.get("smufl", "") if mark.tag == "other-technical" else mark.tag)
    return marks


def _drum_key(sound: str, name: str, head: str) -> int | None:
    if not sound:
        return HAND_CLAP
    if sound == "metal.hi-hat" and "pedal" in name.lower():
        return PEDAL_HI_HAT
    return HEAD_KEYS.get((sound, head), DRUM_KEYS.get(sound))


def drum_keys(root: ET.Element, result: SoundsResult) -> None:
    """Give every percussion entry the General MIDI key of its sound.

    The engraving copy numbers the entries of a kit only to tell them apart (ADR 0008). An
    open or half open hi-hat gets an entry of its own with the open hi-hat key. The notes of
    a single instrument name their instrument, because without it MuseScore plays a note at
    the key of its staff position.
    """
    parts = {part.get("id"): part for part in root.findall("part")}
    for score_part in root.findall("part-list/score-part"):
        part = parts.get(score_part.get("id"))
        if part is None or not _is_percussion(part):
            continue
        instruments = {si.get("id", ""): si for si in score_part.findall("score-instrument")}
        notes = [n for n in part.iter("note") if n.find("unpitched") is not None]
        if len(instruments) == 1:
            only = next(iter(instruments))
            for note in notes:
                if note.find("instrument") is None:
                    after = [i for i, c in enumerate(note) if c.tag in ("duration", "tie")]
                    position = after[-1] + 1 if after else len(note)
                    note.insert(position, ET.Element("instrument", {"id": only}))
        _open_hi_hats(score_part, instruments, notes, result)
        positions: dict[str, list[int]] = {}
        for note in notes:
            ref = note.find("instrument")
            if ref is not None:
                positions.setdefault(ref.get("id", ""), []).append(_position(note))
        toms = _tom_keys(instruments, positions)
        for midi in score_part.findall("midi-instrument"):
            iid = midi.get("id", "")
            instrument = instruments.get(iid)
            if instrument is None:
                continue
            name = instrument.findtext("instrument-name") or iid
            sound = instrument.findtext("instrument-sound") or ""
            head = name.rsplit("(", 1)[1].rstrip(")") if name.endswith(")") else "normal"
            if iid.endswith("-open"):
                key = OPEN_HI_HAT
            elif iid in toms:
                key = toms[iid]
            else:
                key = _drum_key(sound, name, head)
            if key is None:
                result.unmapped.append(name)
                continue
            unpitched = midi.find("midi-unpitched")
            if unpitched is None:
                unpitched = ET.SubElement(midi, "midi-unpitched")
            # MusicXML counts the keys from 1.
            unpitched.text = str(key + 1)
            result.drum_keys += 1


def _tom_keys(
    instruments: dict[str, ET.Element], positions: dict[str, list[int]]
) -> dict[str, int]:
    def name(iid: str) -> str:
        return (instruments[iid].findtext("instrument-name") or "").lower()

    def highest_first(iid: str) -> float:
        found = positions.get(iid, [])
        return -sum(found) / len(found) if found else 0

    toms = [
        iid for iid, si in instruments.items() if si.findtext("instrument-sound") == "drum.tom-tom"
    ]
    keys = {}
    for floor, choices in ((False, RACK_TOMS), (True, FLOOR_TOMS)):
        group = sorted((t for t in toms if ("floor" in name(t)) == floor), key=highest_first)
        for index, iid in enumerate(group):
            keys[iid] = choices[min(index, len(choices) - 1)]
    return keys


def _open_hi_hats(
    score_part: ET.Element,
    instruments: dict[str, ET.Element],
    notes: list[ET.Element],
    result: SoundsResult,
) -> None:
    for note in notes:
        ref = note.find("instrument")
        if ref is None:
            continue
        iid = ref.get("id", "")
        instrument = instruments.get(iid)
        if instrument is None or instrument.findtext("instrument-sound") != "metal.hi-hat":
            continue
        marks = _technical(note)
        if "open" not in marks and not any(m.startswith("pictHalfOpen") for m in marks):
            continue
        open_id = f"{iid}-open"
        if open_id not in instruments:
            entry = copy.deepcopy(instrument)
            entry.set("id", open_id)
            label = entry.find("instrument-name")
            if label is not None:
                label.text = f"{label.text} open"
            score_part.insert(list(score_part).index(instrument) + 1, entry)
            instruments[open_id] = entry
            midi = ET.Element("midi-instrument", {"id": open_id})
            ET.SubElement(midi, "midi-channel").text = "10"
            ET.SubElement(midi, "midi-unpitched").text = str(OPEN_HI_HAT + 1)
            last = score_part.findall("midi-instrument")
            position = list(score_part).index(last[-1]) + 1 if last else len(score_part)
            score_part.insert(position, midi)
        ref.set("id", open_id)
        result.open_hi_hats += 1


def first_sound(root: ET.Element) -> Fraction | None:
    """Where the first note of a pitched part starts, in quarters from the start."""
    first = None
    for part in root.findall("part"):
        if _is_percussion(part):
            continue
        offset = Fraction(0)
        divisions = 1
        for measure in part.findall("measure"):
            if first is not None and offset >= first:
                break
            divisions = _divisions(measure, divisions)
            notes, length = _timeline(measure, divisions)
            starts = [start for start, note in notes if note.find("rest") is None]
            if starts:
                start = offset + min(starts)
                first = start if first is None else min(first, start)
                break
            offset += length
    return first


def _rest(length: Fraction, divisions: int, whole: bool) -> ET.Element:
    note = ET.Element("note")
    ET.SubElement(note, "rest", {"measure": "yes"} if whole else {})
    ET.SubElement(note, "duration").text = str(int(length * divisions))
    ET.SubElement(note, "voice").text = "1"
    if not whole and length in TYPES:
        ET.SubElement(note, "type").text = TYPES[length]
    return note


def _click(length: Fraction, divisions: int) -> ET.Element:
    note = ET.Element("note")
    unpitched = ET.SubElement(note, "unpitched")
    ET.SubElement(unpitched, "display-step").text = "E"
    ET.SubElement(unpitched, "display-octave").text = "4"
    ET.SubElement(note, "duration").text = str(int(length * divisions))
    ET.SubElement(note, "instrument", {"id": f"{COUNT_IN_ID}-I"})
    ET.SubElement(note, "voice").text = "1"
    if length in TYPES:
        ET.SubElement(note, "type").text = TYPES[length]
    return note


def _fill(measure: ET.Element, step: Fraction, count: int, length: Fraction, divisions: int) -> int:
    """``count`` clicks of ``step`` quarters, then a rest to the end of the measure."""
    for _ in range(count):
        measure.append(_click(step, divisions))
    rest = length - count * step
    if count == 0:
        measure.append(_rest(length, divisions, whole=True))
    elif rest > 0:
        measure.append(_rest(rest, divisions, whole=False))
    return count


def count_in(root: ET.Element, result: SoundsResult, settings: CountIn) -> None:
    """Count in on a part of its own: "1 - 2 - 1 2 3 4" in 4/4.

    The count-in is a bar of clicks on every second beat, then a bar of clicks on every beat
    up to the first note of a pitched part. When the first bar is silent at its start, its
    own beats count in and one bar is added before it. When the music starts on its first
    beat, two bars are added. The added bars are not counted, so the bar numbers stay those
    of the parts, and the first one carries the tempo of the first bar.
    """
    parts = root.findall("part")
    firsts = [part.find("measure") for part in parts]
    if not parts or any(first is None for first in firsts):
        return
    attributes = firsts[0].find("attributes")
    divisions = _divisions(firsts[0], 1)
    beats = int(attributes.findtext("time/beats") or 4) if attributes is not None else 4
    beat_type = int(attributes.findtext("time/beat-type") or 4) if attributes is not None else 4
    beat = Fraction(4, beat_type)
    bar = beats * beat
    start = first_sound(root)
    lead_in = bar if start is None else min(start, bar)
    added = 1 if lead_in > 0 else 2
    tempo = next((s.get("tempo") for s in firsts[0].iter("sound") if s.get("tempo")), None)

    for part, first in zip(parts, firsts, strict=True):
        own = first.find("attributes")
        for index in range(added):
            measure = ET.Element("measure", {"number": str(index - added + 1), "implicit": "yes"})
            if own is not None:
                measure.append(copy.deepcopy(own))
            if tempo and index == 0 and part is parts[0]:
                ET.SubElement(measure, "sound", {"tempo": tempo})
            measure.append(_rest(bar, _divisions(first, divisions), whole=True))
            part.insert(index, measure)

    slow = beat * 2 if beats % 2 == 0 else beat
    total = 0
    measures = _count_in_part(root, parts[0], settings)
    for index, (measure, length, divs) in enumerate(measures):
        if index == 0:
            total += _fill(measure, slow, int(length / slow), length, divs)
        elif index == 1 and added == 2:
            total += _fill(measure, beat, int(length / beat), length, divs)
        elif index == 1:
            count = 0
            while count * beat < lead_in and (count + 1) * beat <= length:
                count += 1
            total += _fill(measure, beat, count, length, divs)
        else:
            _fill(measure, beat, 0, length, divs)
    result.count_in_bars = added
    result.count_in_clicks = total


def _count_in_part(
    root: ET.Element, template: ET.Element, settings: CountIn
) -> list[tuple[ET.Element, Fraction, int]]:
    """An empty count-in part with the measures, metres and keys of ``template``.

    Returns every measure with its length in quarters and its divisions.
    """
    part_list = root.find("part-list")
    score_part = ET.SubElement(part_list, "score-part", {"id": COUNT_IN_ID})
    ET.SubElement(score_part, "part-name").text = COUNT_IN_NAME
    instrument = ET.SubElement(score_part, "score-instrument", {"id": f"{COUNT_IN_ID}-I"})
    ET.SubElement(instrument, "instrument-name").text = COUNT_IN_NAME
    midi = ET.SubElement(score_part, "midi-instrument", {"id": f"{COUNT_IN_ID}-I"})
    ET.SubElement(midi, "midi-channel").text = "10"
    ET.SubElement(midi, "midi-unpitched").text = str(settings.key + 1)

    part = ET.SubElement(root, "part", {"id": COUNT_IN_ID})
    measures = []
    divisions = 1
    for index, source in enumerate(template.findall("measure")):
        divisions = _divisions(source, divisions)
        _, length = _timeline(source, divisions)
        measure = ET.SubElement(part, "measure", dict(source.attrib))
        own = source.find("attributes")
        if own is not None or index == 0:
            attributes = ET.SubElement(measure, "attributes")
            for tag in ("divisions", "key", "time"):
                for element in own.findall(tag) if own is not None else []:
                    attributes.append(copy.deepcopy(element))
            if index == 0:
                clef = ET.SubElement(attributes, "clef")
                ET.SubElement(clef, "sign").text = "percussion"
                details = ET.SubElement(attributes, "staff-details")
                ET.SubElement(details, "staff-lines").text = "1"
                loud = ET.SubElement(measure, "direction")
                kind = ET.SubElement(ET.SubElement(loud, "direction-type"), "dynamics")
                ET.SubElement(kind, settings.dynamic)
        measures.append((measure, length, divisions))
    return measures


def prepare_sounds(root: ET.Element, settings: AudioSettings) -> SoundsResult:
    """Turn the prepared copy ``root`` in place into the sounding copy of ``settings``."""
    result = SoundsResult()
    result.transposed = transpose_to_sounding(root, settings.transpose)
    drum_keys(root, result)
    result.unisons = tag_unisons(root, part_sounds(root, settings))
    if settings.count_in is not None:
        count_in(root, result, settings.count_in)
    return result


def _midi_pitch(note: ET.Element) -> int:
    pitch = note.find("pitch")
    step = STEPS.index(pitch.findtext("step") or "C")
    semitones = (0, 2, 4, 5, 7, 9, 11)[step]
    alter = round(float(pitch.findtext("alter") or 0))
    return 12 * (int(pitch.findtext("octave") or 4) + 1) + semitones + alter


def _sample_key(instrument: str, chosen: Sound | None) -> tuple:
    """What tells the samples of a part apart: its sound, or MuseScore's choice for it."""
    if chosen is None:
        return ("MuseScore", instrument)
    if chosen.program is None:
        return (chosen, instrument)
    return (chosen,)


def _sounding_notes(part: ET.Element) -> list[tuple[Fraction, int, Fraction, list[ET.Element]]]:
    """Start, sounding pitch, length and notes of every sound of a pitched part.

    Notes tied to a note before them continue its sound instead of starting one.
    """
    events: list[list] = []
    open_ties: dict[int, list] = {}
    offset = Fraction(0)
    divisions, shift = 1, 0
    for measure in part.findall("measure"):
        divisions = _divisions(measure, divisions)
        for transpose in measure.iter("transpose"):
            chromatic = int(transpose.findtext("chromatic") or 0)
            shift = chromatic + 12 * int(transpose.findtext("octave-change") or 0)
        notes, length = _timeline(measure, divisions)
        for start, note in notes:
            if note.find("pitch") is None or note.find("grace") is not None:
                continue
            pitch = _midi_pitch(note) + shift
            duration = Fraction(int(note.findtext("duration") or 0), divisions)
            ties = {tie.get("type") for tie in note.findall("tie")}
            event = open_ties.pop(pitch, None) if "stop" in ties else None
            if event is None:
                event = [offset + start, pitch, Fraction(0), []]
                events.append(event)
            event[2] += duration
            event[3].append(note)
            if "start" in ties:
                open_ties[pitch] = event
        offset += length
    return [tuple(event) for event in events]


def tag_unisons(root: ET.Element, sounds: list[Sound | None]) -> int:
    """Mark the notes that parts with the same samples play in unison, by a colour per group.

    Two parts that play one note at the same time with the same samples add two identical
    waves, which cancel each other in part and sound hollow or quacking. The colour of a
    note reaches MuseScore's file, where ``xsatz.mscz.play_unisons_once`` lets one part of
    every group sound. Notes start, pitch and length must agree, ties included. Returns
    the number of groups.
    """
    instrument = instrument_sounds(root)
    ids = [sp.get("id") for sp in root.findall("part-list/score-part")]
    groups: dict[tuple, dict[int, list[ET.Element]]] = {}
    for part in root.findall("part"):
        for note in part.iter("note"):
            note.attrib.pop("color", None)
        if _is_percussion(part) or part.get("id") not in ids:
            continue
        index = ids.index(part.get("id"))
        key = _sample_key(instrument[index], sounds[index])
        for start, pitch, length, notes in _sounding_notes(part):
            groups.setdefault((key, start, pitch, length), {}).setdefault(index, []).extend(notes)
    tagged = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        tagged += 1
        colour = f"#{tagged:06X}"
        for notes in members.values():
            for note in notes:
                note.set("color", colour)
    return tagged
