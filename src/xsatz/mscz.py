"""Edit MuseScore files between import and export (ADR 0008, ADR 0009).

Some layout needs elements that MusicXML cannot carry into MuseScore, such as a frame that
exists on the first page only. They are added to MuseScore's own file after the import. The
parts MuseScore extracts from the score get their style and title block here as well.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Height of the frame and lowering of its text in staff spaces. With the score style this
# puts the copyright line 5 mm above the bottom edge of the paper, inside the area that
# common printers still print.
FRAME_HEIGHT = "1"
TEXT_OFFSET = "-0.2"


def _read(mscz: Path) -> tuple[dict[str, bytes], str]:
    """All entries of ``mscz`` and the name of its score entry."""
    with zipfile.ZipFile(mscz) as archive:
        entries = {item: archive.read(item) for item in archive.namelist()}
    return entries, next(name for name in entries if name.endswith(".mscx"))


def _write(mscz: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(mscz, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries.items():
            archive.writestr(item, data)


def add_copyright_frame(mscz: str | Path, text: str) -> bool:
    """Put ``text`` in a frame under the system of the first page of ``mscz``, in place.

    MuseScore has no margins for the first page alone, so a footer would need a bottom
    margin on every page. A frame after the first system takes room on page 1 only. The
    page break of that system moves into the frame. Returns whether the frame was added.
    """
    mscz = Path(mscz)
    entries, name = _read(mscz)
    root = ET.fromstring(entries[name])
    score = root.find("Score")
    staff = score.find("Staff[@id='1']") if score is not None else None
    if staff is None or not text:
        return False

    frame = ET.Element("VBox")
    ET.SubElement(frame, "height").text = FRAME_HEIGHT
    line = ET.SubElement(frame, "Text")
    ET.SubElement(line, "style").text = "copyright"
    ET.SubElement(line, "offset", {"x": "0", "y": TEXT_OFFSET})
    ET.SubElement(line, "text").text = text

    position = len(staff)
    for index, element in enumerate(staff):
        if element.tag != "Measure":
            continue
        found = _page_break(element)
        if found is not None:
            parent, layout_break = found
            parent.remove(layout_break)
            frame.append(layout_break)
            position = index + 1
            break
    staff.insert(position, frame)

    entries[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    _write(mscz, entries)
    return True


def shrink_blank_lines(mscz: str | Path, style: str = "composer", factor: float = 0.5) -> int:
    """Set the empty lines of the texts with ``style`` in ``factor`` of their font size.

    An empty line sets groups of the credit block apart, a full line height is more than
    the block needs. MuseScore takes the height of a line from the size of its characters,
    so a small character on the empty line and the style size after it make a narrower
    gap. Returns the number of empty lines changed.
    """
    mscz = Path(mscz)
    entries, name = _read(mscz)
    style_file = ET.fromstring(entries.get("score_style.mss", b"<museScore/>"))
    size_text = style_file.findtext(f"Style/{style}FontSize")
    if not size_text:
        return 0
    size = float(size_text)
    root = ET.fromstring(entries[name])
    changed = 0
    for text_element in root.iter("Text"):
        if text_element.findtext("style") != style:
            continue
        text = text_element.find("text")
        if text is None:
            continue
        children = list(text)
        for index in range(len(children) - 1, 0, -1):
            first, second = children[index - 1], children[index]
            if first.tag == "br" and second.tag == "br" and not (first.tail or "").strip():
                small = ET.Element("font", {"size": f"{size * factor:g}"})
                # MuseScore measures a line by its characters and drops plain spaces, so the
                # empty line carries a no-break space in the small size.
                small.tail = " "
                normal = ET.Element("font", {"size": f"{size:g}"})
                normal.tail, second.tail = second.tail, None
                position = list(text).index(second)
                text.insert(position, small)
                text.insert(position + 2, normal)
                changed += 1
    if changed:
        entries[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        _write(mscz, entries)
    return changed


def _page_break(measure: ET.Element) -> tuple[ET.Element, ET.Element] | None:
    for parent in measure.iter():
        for child in parent:
            if child.tag == "LayoutBreak" and child.findtext("subtype") == "page":
                return parent, child
    return None


# A line of text needs about 1.2 times its font size.
LINE_HEIGHT = 1.2
# Gap between the title and the credit lines under it, in staff spaces.
TITLE_GAP = 0.5
# The distance between systems in both of MuseScore's layouts. The largest equals the smallest,
# so that MuseScore does not spread the systems of a page that is not full, and every page of
# a part keeps the same distance.
SYSTEM_DISTANCES = ("minSystemDistance", "maxSystemDistance", "minSystemSpread", "maxSystemSpread")


def _style_value(style: ET.Element, key: str) -> float:
    return float(style.findtext(f"Style/{key}") or 0)


def edit_part(mscz: str | Path, name: str, style: str | Path) -> None:
    """Turn a part that MuseScore extracted from the full score into an X-Satz part, in place.

    The part file carries a style of its own inside the score entry, which wins over
    ``score_style.mss``, so it is removed and ``score_style.mss`` replaced by ``style``. The
    label of the title block, "full score" in the score, becomes ``name``, and MuseScore's
    own small part name above the title goes. The title frame grows until the credit lines
    fit under the title, because at portrait width a long title runs into them.
    """
    mscz = Path(mscz)
    entries, entry = _read(mscz)
    style_data = Path(style).read_bytes()
    entries["score_style.mss"] = style_data
    style_root = ET.fromstring(style_data)
    root = ET.fromstring(entries[entry])
    score = root.find("Score")
    if score is None:
        raise ValueError(f"{mscz}: no score in the file")
    for inline in score.findall("Style"):
        score.remove(inline)
    _drop_font_faces(score)

    frame = next(score.iter("VBox"), None)
    if frame is not None:
        label = None
        for text in frame.findall("Text"):
            kind = text.findtext("style")
            if kind == "instrument_excerpt":
                frame.remove(text)
            elif kind in ("poet", "lyricist"):
                label = text
        if label is None:
            label = ET.SubElement(frame, "Text")
            ET.SubElement(label, "style").text = "poet"
            ET.SubElement(label, "text")
        label.find("text").text = name
        _fit_title_frame(frame, style_root)

    entries[entry] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    _write(mscz, entries)


def _drop_font_faces(score: ET.Element) -> None:
    """Remove the font families written into single texts, such as tempo marks.

    The import writes the font family of the MusicXML into some texts, which then ignore the
    fonts of the part style.
    """
    for text in score.iter("text"):
        for font in list(text.iter("font")):
            if "face" not in font.attrib:
                continue
            del font.attrib["face"]
            if not font.attrib:
                _remove_keeping_tail(text, font)


def _remove_keeping_tail(root: ET.Element, element: ET.Element) -> None:
    """Remove ``element`` below ``root`` and keep the text that follows it."""
    for parent in root.iter():
        children = list(parent)
        if element not in children:
            continue
        index = children.index(element)
        tail = element.tail or ""
        if index == 0:
            parent.text = (parent.text or "") + tail
        else:
            previous = children[index - 1]
            previous.tail = (previous.tail or "") + tail
        parent.remove(element)
        return


def _fit_title_frame(frame: ET.Element, style: ET.Element) -> None:
    """Make ``frame`` tall enough for the title above the credit lines.

    MuseScore sets the title at the top of the frame and the credits at its bottom, so the
    frame needs the height of both and a small gap between them. An empty line of the
    credits counts half, see shrink_blank_lines. The height is measured in staff spaces.
    """
    lines = sum(
        0.5 if not line.strip() else 1.0
        for text in frame.findall("Text")
        if text.findtext("style") == "composer"
        for line in _lines(text.find("text"))
    )
    points = LINE_HEIGHT * (
        _style_value(style, "titleFontSize") + lines * _style_value(style, "composerFontSize")
    )
    spatium = _style_value(style, "spatium")
    if not spatium:
        return
    needed = points / 72 * 25.4 / spatium + TITLE_GAP
    height = frame.find("height")
    if height is None:
        height = ET.SubElement(frame, "height")
        height.text = "0"
    if needed > float(height.text or 0):
        height.text = f"{needed:.1f}"


def _lines(text: ET.Element | None) -> list[str]:
    """The lines of a MuseScore text, split at its line breaks."""
    if text is None:
        return []
    lines = [text.text or ""]
    for child in text:
        if child.tag == "br":
            lines.append(child.tail or "")
        else:
            lines[-1] += child.tail or ""
    return lines


def system_distance(mscz: str | Path) -> float:
    """Smallest distance between two systems in ``mscz``, in staff spaces."""
    entries, _ = _read(Path(mscz))
    return _style_value(ET.fromstring(entries["score_style.mss"]), SYSTEM_DISTANCES[0])


def set_system_distance(mscz: str | Path, value: float) -> None:
    """Set the smallest distance between two systems of ``mscz`` to ``value`` staff spaces.

    With vertical spread enabled MuseScore keeps systems apart by the spread, without it by
    the distance, so the smallest and largest of both take the value.
    """
    mscz = Path(mscz)
    entries, _ = _read(mscz)
    root = ET.fromstring(entries["score_style.mss"])
    style = root.find("Style")
    for key in SYSTEM_DISTANCES:
        element = style.find(key)
        if element is None:
            element = ET.SubElement(style, key)
        element.text = f"{value:g}"
    entries["score_style.mss"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    _write(mscz, entries)


# Elements whose text MuseScore starts at their measure, however little room is left.
MEASURE_TEXTS = ("SystemText", "StaffText", "RehearsalMark")
# Characters a cut text needs at least to be recognised by its beginning.
PREFIX_LENGTH = 4
# What a PDF reader returns for a glyph it cannot map to a character, such as a swash letter.
UNREADABLE = "�"


def reads_as(seen: str, text: str) -> bool:
    """Whether ``seen``, read from a PDF, shows ``text``, an unreadable glyph standing for any."""
    if len(seen) != len(text):
        return False
    return all(a in (b, UNREADABLE) for a, b in zip(seen, text, strict=True))


def break_before_text(mscz: str | Path, text: str) -> bool:
    """Start a new system at the measure that carries ``text``, in place.

    MuseScore sets a system text, staff text or rehearsal mark from the start of its measure
    and lets it run past the right margin when that measure ends a narrow system. A system
    break after the previous measure moves the text to the start of the next system.
    ``text`` may be the beginning of the text only, because a PDF holds no glyphs beyond the
    edge of the paper. Returns whether a break was added: not when no such text exists, when
    its measure is the first one or when the previous measure already ends a system.
    """
    mscz = Path(mscz)
    entries, entry = _read(mscz)
    root = ET.fromstring(entries[entry])
    wanted = text.strip()
    # MuseScore stores a multi-measure rest as an extra measure after its first one.
    measures = [
        [m for m in staff.iter("Measure") if m.find("multiMeasureRest") is None]
        for staff in root.iterfind("Score/Staff")
    ]
    # A whole text wins over one it only begins, and a short beginning such as a single
    # digit could begin too many texts to count.
    for matches in (
        lambda found: reads_as(wanted, found),
        lambda found: len(wanted) >= PREFIX_LENGTH and reads_as(wanted, found[: len(wanted)]),
    ):
        for staff in measures:
            for index, measure in enumerate(staff):
                if not any(matches(found) for found in _measure_texts(measure)):
                    continue
                if index == 0:
                    return False
                previous = staff[index - 1]
                if previous.find("LayoutBreak") is not None:
                    return False
                layout_break = ET.Element("LayoutBreak")
                ET.SubElement(layout_break, "subtype").text = "line"
                eid = previous.find("eid")
                previous.insert(0 if eid is None else list(previous).index(eid) + 1, layout_break)
                entries[entry] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                _write(mscz, entries)
                return True
    return False


def _measure_texts(measure: ET.Element) -> list[str]:
    return [
        "".join(text.itertext()).strip()
        for kind in MEASURE_TEXTS
        for element in measure.iter(kind)
        if (text := element.find("text")) is not None
    ]


@dataclass
class MarkGroup:
    """A rehearsal mark and the texts MuseScore stacks above it at the same measure."""

    mark: str
    # Plain texts of the system texts and tempo marks at the mark, in the order of the file.
    texts: list[str] = field(default_factory=list)
    # Which of the texts are tempo marks.
    tempo: list[bool] = field(default_factory=list)


GROUPED = ("SystemText", "Tempo")


def _plain(element: ET.Element) -> str:
    """The characters of the text of ``element``, without its symbols and font changes.

    A symbol such as the note of a tempo mark is stored by its name, which the PDF does not
    show, so it is left out.
    """
    text = element.find("text")
    if text is None:
        return ""
    parts = [text.text or ""]
    for child in text.iter():
        if child is not text:
            parts.append(child.tail or "")
    return "".join(parts).strip()


def _mark_measures(root: ET.Element) -> list[tuple[ET.Element, list[ET.Element]]]:
    """Rehearsal marks with the system texts and tempo marks of their measure."""
    found = []
    for staff in root.iterfind("Score/Staff"):
        for measure in staff.iter("Measure"):
            if measure.find("multiMeasureRest") is not None:
                continue
            for mark in measure.iter("RehearsalMark"):
                texts = [e for e in measure.iter() if e.tag in GROUPED and _plain(e)]
                found.append((mark, texts))
    return found


def mark_groups(mscz: str | Path) -> list[MarkGroup]:
    """The rehearsal marks of ``mscz`` that carry other texts at their measure."""
    entries, entry = _read(Path(mscz))
    return [
        MarkGroup(_plain(mark), [_plain(text) for text in texts], [t.tag == "Tempo" for t in texts])
        for mark, texts in _mark_measures(ET.fromstring(entries[entry]))
        if texts
    ]


def place_beside_mark(mscz: str | Path, mark: str, shifts: list[tuple[float, float]]) -> bool:
    """Move the texts at the rehearsal mark ``mark`` by ``shifts``, in place.

    MuseScore stacks a section title and a tempo mark above the rehearsal mark of their
    measure, which pushes the system far away from the one above. ``shifts`` holds a move
    sideways and down for every text, in staff spaces and in the order of ``mark_groups``.
    A text that still stands where the style puts it starts on the height of the mark,
    because its place in the stack comes from MuseScore and not from its offset, and only
    moves sideways. Returns whether the mark was found.
    """
    mscz = Path(mscz)
    entries, entry = _read(mscz)
    root = ET.fromstring(entries[entry])
    style = ET.fromstring(entries["score_style.mss"])
    for found, texts in _mark_measures(root):
        if _plain(found) != mark or len(texts) != len(shifts):
            continue
        height = _offset(found, style, "rehearsalMark")[1]
        for text, (right, down) in zip(texts, shifts, strict=True):
            kind = "systemText" if text.tag == "SystemText" else "tempo"
            x, y = _offset(text, style, kind)
            offset = text.find("offset")
            if offset is None:
                offset = ET.Element("offset")
                text.insert(list(text).index(text.find("text")), offset)
                y, down = height, 0.0
            offset.attrib = {"x": f"{x + right:.3f}", "y": f"{y + down:.3f}"}
        entries[entry] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        _write(mscz, entries)
        return True
    return False


def _offset(element: ET.Element, style: ET.Element, kind: str) -> tuple[float, float]:
    """Offset of ``element`` in staff spaces, its own or the default of its style above."""
    offset = element.find("offset")
    if offset is None:
        offset = style.find(f"Style/{kind}PosAbove")
    if offset is None:
        return 0.0, 0.0
    return float(offset.get("x", 0)), float(offset.get("y", 0))
