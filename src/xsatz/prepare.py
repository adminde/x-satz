"""Prepare a copy of a MusicXML file before MuseScore reads it (ADR 0008).

Each step answers a finding of phase 1: Dorico's credits break the page layout in MuseScore,
its combined directions lose rehearsal marks, and its metadata hold placeholders.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from xsatz import __version__
from xsatz.xmlinfo import load

DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)


@dataclass
class Titles:
    """Texts of the title block, taken from the MusicXML of the piece."""

    title: str = ""
    label: str = ""
    lines: list[str] = field(default_factory=list)
    rights: str = ""
    # How many of the lines name the arranger. The block sets them apart from the rest.
    arranger_lines: int = 0


@dataclass
class PrepareResult:
    source: Path
    target: Path
    titles: Titles
    credits_removed: int = 0
    directions_split: int = 0
    font_sizes_dropped: int = 0
    kit_entries: int = 0
    percussion_keys_hidden: int = 0
    percussion_channels_added: int = 0
    names_stripped: int = 0
    groups_added: int = 0
    page_layout_from_style: bool = False
    fonts_from_style: int = 0
    software_replaced: int = 0


def _text(element: ET.Element) -> str:
    return " ".join((w.text or "").strip() for w in element.findall("credit-words")).strip()


def read_titles(root: ET.Element) -> Titles:
    """Title, label, credit lines and copyright from the page 1 credits or the metadata."""
    by_type: dict[str, list[str]] = {}
    for credit in root.findall("credit"):
        if credit.get("page", "1") != "1":
            continue
        text = _text(credit)
        if text:
            by_type.setdefault(credit.findtext("credit-type") or "", []).append(text)

    def first(kind: str) -> str:
        return by_type.get(kind, [""])[0]

    # Dorico keeps the placeholder of the flow in movement-title, the title of the work
    # is the reliable fallback.
    title = first("title") or root.findtext("work/work-title") or ""
    title = title or root.findtext("movement-title") or ""
    arrangers = by_type.get("arranger", [])
    lines = arrangers + by_type.get("composer", []) + by_type.get("", [])
    if not lines:
        lines = [c.text.strip() for c in root.findall("identification/creator") if c.text]
    rights = first("rights") or (root.findtext("identification/rights") or "").strip()
    return Titles(
        title=title,
        label=first("part name"),
        lines=lines,
        rights=rights,
        arranger_lines=len(arrangers),
    )


def _remove_credits(root: ET.Element) -> int:
    credits = root.findall("credit")
    for credit in credits:
        root.remove(credit)
    return len(credits)


def _write_metadata(root: ET.Element, titles: Titles) -> None:
    work = root.find("work")
    if work is None:
        work = ET.Element("work")
        root.insert(0, work)
    work_title = work.find("work-title")
    if work_title is None:
        work_title = ET.SubElement(work, "work-title")
    work_title.text = titles.title
    movement = root.find("movement-title")
    if movement is None:
        movement = ET.Element("movement-title")
        root.insert(list(root).index(work) + 1, movement)
    movement.text = titles.title

    ident = root.find("identification")
    if ident is None:
        ident = ET.Element("identification")
        root.insert(list(root).index(movement) + 1, ident)
    for old in ident.findall("creator") + ident.findall("rights"):
        ident.remove(old)
    # MusicXML requires creators first and rights after them inside identification.
    new = []
    if titles.lines:
        arrangers, rest = (
            titles.lines[: titles.arranger_lines],
            titles.lines[titles.arranger_lines :],
        )
        # An empty line sets the arranger apart from adaptation and dedication.
        groups = [group for group in ("\n".join(arrangers), "\n".join(rest)) if group]
        new.append(("creator", {"type": "composer"}, "\n\n".join(groups)))
    if titles.label:
        new.append(("creator", {"type": "lyricist"}, titles.label))
    if titles.rights:
        new.append(("rights", {}, titles.rights))
    for position, (tag, attrib, text) in enumerate(new):
        element = ET.Element(tag, attrib)
        element.text = text
        ident.insert(position, element)


def _split_directions(root: ET.Element) -> int:
    split = 0
    for measure in root.iter("measure"):
        for index, direction in reversed(list(enumerate(measure))):
            if direction.tag != "direction":
                continue
            types = direction.findall("direction-type")
            if len(types) < 2:
                continue
            types.sort(key=lambda t: t.find("rehearsal") is None)
            measure.remove(direction)
            for offset, kind in enumerate(types):
                single = copy.deepcopy(direction)
                for old in single.findall("direction-type"):
                    single.remove(old)
                # A sound element belongs to the tempo only, not to the texts beside it.
                if kind.find("metronome") is None:
                    for sound in single.findall("sound"):
                        single.remove(sound)
                single.insert(0, copy.deepcopy(kind))
                measure.insert(index + offset, single)
            split += 1
    # Dorico prints rehearsal marks bold. MuseScore marks the imported text as not bold
    # unless the MusicXML says so, and that wins over the style.
    for mark in root.iter("rehearsal"):
        mark.text = (mark.text or "").strip()
        mark.set("font-weight", mark.get("font-weight", "bold"))
    return split


def _percussion_parts(root: ET.Element) -> list[ET.Element]:
    return [
        part
        for part in root.findall("part")
        if part.findtext("measure/attributes/clef/sign") == "percussion"
    ]


def _kit_entries(root: ET.Element) -> int:
    """Turn every instrument and notehead of a percussion kit into one drum set entry.

    Without MIDI data MuseScore reads every change of kit instrument as an instrument change
    and puts the voices of the kit into one voice. With MIDI data it builds one drum set,
    but gives every entry a single notehead, so a snare with normal, diamond and x heads
    would print all of them alike. One entry per instrument and notehead, each with its own
    drum key on the percussion channel 10, keeps Dorico's voices, noteheads and positions.
    The drum keys only tell the entries apart and are no General MIDI sounds.
    """
    entries = 0
    parts = {part.get("id"): part for part in _percussion_parts(root)}
    for score_part in root.findall("part-list/score-part"):
        instruments = score_part.findall("score-instrument")
        part = parts.get(score_part.get("id"))
        if part is None or len(instruments) < 2:
            continue
        by_id = {instrument.get("id"): instrument for instrument in instruments}
        combos: list[tuple[str, str]] = []
        for note in part.iter("note"):
            reference = note.find("instrument")
            if reference is None or reference.get("id") not in by_id:
                continue
            combo = (reference.get("id"), note.findtext("notehead") or "normal")
            if combo not in combos:
                combos.append(combo)
            reference.set("id", "-".join(combo))
        position = list(score_part).index(instruments[0])
        for old in instruments + score_part.findall("midi-instrument"):
            score_part.remove(old)
        new: list[ET.Element] = []
        for instrument_id, head in combos:
            entry = ET.Element("score-instrument", {"id": f"{instrument_id}-{head}"})
            name = by_id[instrument_id].findtext("instrument-name") or instrument_id
            ET.SubElement(entry, "instrument-name").text = f"{name} ({head})"
            sound = by_id[instrument_id].findtext("instrument-sound")
            if sound:
                ET.SubElement(entry, "instrument-sound").text = sound
            new.append(entry)
        for key, (instrument_id, head) in enumerate(combos):
            midi = ET.Element("midi-instrument", {"id": f"{instrument_id}-{head}"})
            ET.SubElement(midi, "midi-channel").text = "10"
            ET.SubElement(midi, "midi-unpitched").text = str(36 + key)
            new.append(midi)
        for offset, element in enumerate(new):
            score_part.insert(position + offset, element)
        entries += len(combos)
    return entries


def _hide_percussion_keys(root: ET.Element) -> int:
    """Dorico exports the key of the score to percussion staves without showing it there."""
    hidden = 0
    for part in _percussion_parts(root):
        for key in part.iter("key"):
            key.set("print-object", "no")
            hidden += 1
    return hidden


def _percussion_channel(root: ET.Element) -> int:
    """Give single percussion instruments without MIDI data the percussion channel 10.

    Without it MuseScore recognises a percussion staff only by a sound it knows. Dorico's
    timpani with the sound of a kick drum became a pitched piano staff with key signature
    and ledger lines instead of a note on the single line. Kits of several instruments are
    left alone: MuseScore knows their sounds, and the channel would merge their voices.
    """
    added = 0
    ids = {part.get("id") for part in _percussion_parts(root)}
    for score_part in root.findall("part-list/score-part"):
        instruments = score_part.findall("score-instrument")
        if score_part.get("id") not in ids or len(instruments) != 1:
            continue
        instrument = instruments[0]
        if score_part.find("midi-instrument") is not None:
            continue
        midi = ET.Element("midi-instrument", {"id": instrument.get("id", "")})
        ET.SubElement(midi, "midi-channel").text = "10"
        # MuseScore builds its drum set only from a drum key. The bass drum of General MIDI
        # (key 36, counted from 1 in MusicXML) stands in, the printed score does not use it.
        ET.SubElement(midi, "midi-unpitched").text = "37"
        # MusicXML puts midi-instrument after score-instrument and any midi-device.
        anchors = score_part.findall("midi-device") or score_part.findall("score-instrument")
        score_part.insert(list(score_part).index(anchors[-1]) + 1, midi)
        added += 1
    return added


NUMBERED = re.compile(r"^(.*?)\s*\d+$")
IN_C = " (C)"


def _strip_in_c(root: ET.Element) -> int:
    """Remove the suffix " (C)" that Dorico adds to the exported names of C instruments.

    Dorico prints these names without it, so the reference shows "Trompete 1", not
    "Trompete 1 (C)". Other transpositions stay in the name, they matter to the player.
    """
    stripped = 0
    for score_part in root.findall("part-list/score-part"):
        for element in score_part.iter():
            if element.tag in ("part-name", "part-abbreviation", "display-text"):
                if element.text and element.text.endswith(IN_C):
                    element.text = element.text[: -len(IN_C)]
                    stripped += 1
    return stripped


def _group(number: int, kind: str, symbol: str = "", barline: str = "") -> ET.Element:
    group = ET.Element("part-group", {"type": kind, "number": str(number)})
    if symbol:
        ET.SubElement(group, "group-symbol").text = symbol
    if barline:
        ET.SubElement(group, "group-barline").text = barline
    return group


def _add_groups(root: ET.Element) -> int:
    """Bracket the parts like the reference when the MusicXML carries no groups.

    Dorico brackets each family, the pitched instruments and the percussion, and puts a sub
    bracket around neighbouring parts of the same instrument (Trumpet 1 to 3). Barlines run
    through the sub brackets and through a family without sub brackets.
    """
    part_list = root.find("part-list")
    if part_list is None or part_list.find("part-group") is not None:
        return 0
    parts = part_list.findall("score-part")
    percussion = {part.get("id") for part in _percussion_parts(root)}
    families: list[list[ET.Element]] = []
    for part in parts:
        is_percussion = part.get("id") in percussion
        if families and (families[-1][0].get("id") in percussion) == is_percussion:
            families[-1].append(part)
        else:
            families.append([part])

    def stem(part: ET.Element) -> str | None:
        match = NUMBERED.match(part.findtext("part-name") or "")
        return match.group(1) if match else None

    groups = 0
    number = 0
    for family in families:
        subs: list[list[ET.Element]] = []
        for part in family:
            if subs and stem(part) is not None and stem(part) == stem(subs[-1][-1]):
                subs[-1].append(part)
            else:
                subs.append([part])
        subs = [sub for sub in subs if len(sub) > 1]
        if len(family) > 1:
            number += 1
            barline = "no" if subs else "yes"
            index = list(part_list).index(family[0])
            part_list.insert(index, _group(number, "start", "bracket", barline))
            part_list.insert(list(part_list).index(family[-1]) + 1, _group(number, "stop"))
            groups += 1
        for sub in subs:
            number += 1
            part_list.insert(
                list(part_list).index(sub[0]), _group(number, "start", "square", "yes")
            )
            part_list.insert(list(part_list).index(sub[-1]) + 1, _group(number, "stop"))
            groups += 1
    return groups


PAGE_LAYOUT = {
    "page-height": "pageHeight",
    "page-width": "pageWidth",
    "printable-width": "pagePrintableWidth",
    "left-margin": "pageOddLeftMargin",
    "top-margin": "pageOddTopMargin",
    "bottom-margin": "pageOddBottomMargin",
}


def _style_value(style: ET.Element, key: str) -> float | None:
    text = style.findtext(f"Style/{key}")
    return float(text) if text else None


def _page_layout_from_style(root: ET.Element, style_path: Path) -> bool:
    """Write page size and margins of the style into the MusicXML.

    MuseScore takes page size and margins from the MusicXML and ignores those of a style
    passed with -S. Without them in the MusicXML it uses its own defaults, so the style can
    only reach the page through the copy. The style stays the one place for the layout.
    """
    defaults = root.find("defaults")
    if defaults is None:
        return False
    millimeters = defaults.findtext("scaling/millimeters")
    tenths = defaults.findtext("scaling/tenths")
    if not millimeters or not tenths:
        return False
    per_inch = 25.4 * float(tenths) / float(millimeters)
    style = ET.parse(style_path).getroot()
    inches = {tag: _style_value(style, key) for tag, key in PAGE_LAYOUT.items()}
    if None in inches.values():
        return False
    # A MuseScore style has no right margin, it follows from the printable width.
    inches["right-margin"] = (
        inches["page-width"] - inches["left-margin"] - inches["printable-width"]
    )
    for old in defaults.findall("page-layout"):
        defaults.remove(old)
    layout = ET.Element("page-layout")
    ET.SubElement(layout, "page-height").text = f"{inches['page-height'] * per_inch:.2f}"
    ET.SubElement(layout, "page-width").text = f"{inches['page-width'] * per_inch:.2f}"
    margins = ET.SubElement(layout, "page-margins", {"type": "both"})
    for side in ("left", "right", "top", "bottom"):
        value = inches[f"{side}-margin"] * per_inch
        ET.SubElement(margins, f"{side}-margin").text = f"{value:.2f}"
    scaling = defaults.find("scaling")
    defaults.insert(list(defaults).index(scaling) + 1, layout)
    return True


def _drop_default_font_sizes(root: ET.Element) -> int:
    """Keep the font families of the defaults but leave the sizes to the style.

    MuseScore lets the default sizes of the MusicXML override the text sizes of the style,
    and without the families it falls back to its own typeface instead of the style's.
    """
    dropped = 0
    for tag in ("music-font", "word-font", "lyric-font"):
        for font in root.findall(f"defaults/{tag}"):
            if "font-size" in font.attrib:
                del font.attrib["font-size"]
                dropped += 1
    return dropped


def _fonts_from_style(root: ET.Element, style_path: Path) -> int:
    """Write the text font of the style into the defaults and drop the fonts of single texts.

    MuseScore takes the font families of the MusicXML over the fonts of a style passed with
    -S, both those of the defaults and those written on single texts. Without a family in the
    defaults it falls back to its own typeface, so the defaults name the font of the style.
    Returns the number of fonts changed or dropped.
    """
    defaults = root.find("defaults")
    if defaults is None:
        return 0
    family = ET.parse(style_path).getroot().findtext("Style/defaultFontFace")
    if not family:
        return 0
    changed = 0
    for tag in ("word-font", "lyric-font"):
        font = defaults.find(tag)
        if font is None:
            font = ET.Element(tag)
            music = defaults.find("music-font")
            position = list(defaults).index(music) + 1 if music is not None else len(defaults)
            defaults.insert(position, font)
        font.set("font-family", family)
        changed += 1
    for part in root.findall("part"):
        for element in part.iter():
            if "font-family" in element.attrib:
                del element.attrib["font-family"]
                changed += 1
    return changed


def _replace_software(root: ET.Element) -> int:
    encoding = root.find("identification/encoding")
    if encoding is None:
        return 0
    entries = encoding.findall("software")
    for entry in entries:
        encoding.remove(entry)
    software = ET.Element("software")
    software.text = f"X-Satz {__version__}"
    encoding.insert(0, software)
    return len(entries)


def prepare(
    source: str | Path, target: str | Path, style: str | Path | None = None
) -> PrepareResult:
    """Write a prepared copy of ``source`` to ``target``. ``source`` is never changed.

    With ``style`` the page size, margins and text font of that MuseScore style go into the
    copy.
    """
    source, target = Path(source), Path(target)
    if target.resolve() == source.resolve():
        raise ValueError(f"{source}: preparing must not overwrite the original")
    root = copy.deepcopy(load(source))
    titles = read_titles(root)
    result = PrepareResult(source=source, target=target, titles=titles)
    result.credits_removed = _remove_credits(root)
    _write_metadata(root, titles)
    result.directions_split = _split_directions(root)
    result.font_sizes_dropped = _drop_default_font_sizes(root)
    result.percussion_channels_added = _percussion_channel(root)
    result.kit_entries = _kit_entries(root)
    result.percussion_keys_hidden = _hide_percussion_keys(root)
    result.names_stripped = _strip_in_c(root)
    result.groups_added = _add_groups(root)
    if style is not None:
        result.page_layout_from_style = _page_layout_from_style(root, Path(style))
        result.fonts_from_style = _fonts_from_style(root, Path(style))
    result.software_replaced = _replace_software(root)

    body = ET.tostring(root, encoding="unicode")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n{body}\n', encoding="utf-8"
    )
    return result
