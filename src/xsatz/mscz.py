"""Edit MuseScore files between import and export (ADR 0008).

Some layout needs elements that MusicXML cannot carry into MuseScore, such as a frame that
exists on the first page only. They are added to MuseScore's own file after the import.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# Height of the frame and lowering of its text in staff spaces. With the score style this
# puts the copyright line 5 mm above the bottom edge of the paper, inside the area that
# common printers still print.
FRAME_HEIGHT = "1"
TEXT_OFFSET = "-0.2"


def _score_file(archive: zipfile.ZipFile) -> str:
    return next(name for name in archive.namelist() if name.endswith(".mscx"))


def add_copyright_frame(mscz: str | Path, text: str) -> bool:
    """Put ``text`` in a frame under the system of the first page of ``mscz``, in place.

    MuseScore has no margins for the first page alone, so a footer would need a bottom
    margin on every page. A frame after the first system takes room on page 1 only. The
    page break of that system moves into the frame. Returns whether the frame was added.
    """
    mscz = Path(mscz)
    with zipfile.ZipFile(mscz) as archive:
        name = _score_file(archive)
        entries = {item: archive.read(item) for item in archive.namelist()}
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
    with zipfile.ZipFile(mscz, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries.items():
            archive.writestr(item, data)
    return True


def shrink_blank_lines(mscz: str | Path, style: str = "composer", factor: float = 0.5) -> int:
    """Set the empty lines of the texts with ``style`` in ``factor`` of their font size.

    An empty line sets groups of the credit block apart, a full line height is more than
    the block needs. MuseScore takes the height of a line from the size of its characters,
    so a small character on the empty line and the style size after it make a narrower
    gap. Returns the number of empty lines changed.
    """
    mscz = Path(mscz)
    with zipfile.ZipFile(mscz) as archive:
        name = _score_file(archive)
        entries = {item: archive.read(item) for item in archive.namelist()}
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
        with zipfile.ZipFile(mscz, "w", zipfile.ZIP_DEFLATED) as archive:
            for item, data in entries.items():
                archive.writestr(item, data)
    return changed


def _page_break(measure: ET.Element) -> tuple[ET.Element, ET.Element] | None:
    for parent in measure.iter():
        for child in parent:
            if child.tag == "LayoutBreak" and child.findtext("subtype") == "page":
                return parent, child
    return None
