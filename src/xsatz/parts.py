"""Parts: one PDF per instrument, extracted from the full score by MuseScore (ADR 0009)."""

from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import pymupdf

from xsatz import musescore
from xsatz.mscz import (
    MarkGroup,
    break_before_text,
    edit_part,
    mark_groups,
    place_beside_mark,
    reads_as,
    set_system_distance,
    shrink_blank_lines,
    system_distance,
)
from xsatz.prepare import PrepareResult, prepare
from xsatz.render import default_style

MAX_PAGES = 2
# The systems of a part keep the distance of the part style. Only when that leaves at most
# OVERFLOW_SYSTEMS systems on a page beyond MAX_PAGES do they move closer, to each of the
# FALLBACK_DISTANCES in staff spaces in turn, and back to the style when none of them saves
# the page. The staff size never changes.
FALLBACK_DISTANCES = (10.0, 8.0)
OVERFLOW_SYSTEMS = 2
# MuseScore moves a tempo mark at a rehearsal mark on its own as well, so the texts at the
# marks are measured again after every export and moved by what is left, at most this often,
# until no text is further than ARRANGE_TOLERANCE staff spaces from its place.
ARRANGE_ROUNDS = 4
ARRANGE_TOLERANCE = 0.2
# Gap between a tempo mark and the section title under it, in staff spaces.
LINE_GAP = 0.3
# A text may reach this far into the right margin, in points, before it counts as outside.
# MuseScore aligns texts by the advance width of their glyphs, so the outlines of a text
# set flush right, such as the page number, end a fraction of a point past the margin.
MARGIN_TOLERANCE = 2.0
# Characters that Windows does not allow in file names.
UNSAFE = re.compile(r'[<>:"/\\|?*]')


@dataclass
class Part:
    name: str
    output: Path
    pages: int = 0
    system_distance: float = 0.0
    # System breaks added because a text ran past the right margin.
    breaks: int = 0
    # Texts that still run past the right margin.
    beyond_margin: list[str] = field(default_factory=list)


@dataclass
class PartsResult:
    source: Path
    parts: list[Part]
    log: str
    prepared: PrepareResult | None = None
    # Left page margin of the parts in points, where the logo starts.
    margin: float = 0.0

    @property
    def ok(self) -> bool:
        return bool(self.parts) and all(part.output.exists() for part in self.parts)


def default_part_style() -> Path:
    """The part style that ships with X-Satz."""
    return Path(str(resources.files("xsatz") / "styles" / "part.mss"))


def part_file_name(stem: str, name: str, suffix: str = "pdf") -> str:
    """File name of the part ``name`` of the score ``stem``."""
    return f"{stem} - {UNSAFE.sub('_', name).strip()}.{suffix}"


def render_parts(source: str | Path, out_dir: str | Path | None = None) -> PartsResult:
    """Render every part of ``source`` as a PDF of its own.

    Without ``out_dir`` the parts are written next to ``source``. MuseScore imports a prepared
    copy with the score style, as for the full score (ADR 0008), and extracts the parts from
    its file. Each part gets the part style and is exported. A part whose last page beyond
    MAX_PAGES holds no more than OVERFLOW_SYSTEMS systems is exported again with its systems
    closer, at each of the FALLBACK_DISTANCES in turn.
    After the first export the texts at every rehearsal mark move beside the mark, and the
    part is exported again. A part with a text past the right margin gets a system break
    before the measure of that text and is exported again first.
    """
    source = Path(source)
    out_dir = Path(out_dir) if out_dir is not None else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    score_style, part_style = default_style(), default_part_style()
    margin, right = _margins(part_style)
    spatium = _spatium(part_style)
    with tempfile.TemporaryDirectory(prefix="xsatz-") as work:
        reads = Path(work) / f"{source.stem}.musicxml"
        info = prepare(source, reads, score_style)
        score = Path(work) / f"{source.stem}.mscz"
        log = _run(["-S", str(score_style), "-o", str(score), str(reads)])
        if not score.exists():
            return PartsResult(source, [], log[-2000:], info, margin)
        shrink_blank_lines(score)
        extracted = musescore.run(["--score-parts", str(score)])
        log += extracted.stderr
        pending: list[tuple[Part, Path]] = []
        for index, (name, data) in enumerate(_extracted_parts(extracted.stdout)):
            mscz = Path(work) / f"part-{index}.mscz"
            mscz.write_bytes(data)
            edit_part(mscz, name, part_style)
            part = Part(name, out_dir / part_file_name(source.stem, name))
            part.system_distance = system_distance(mscz)
            pending.append((part, mscz))
        files = list(pending)
        rounds: dict[str, int] = {}
        settled: set[str] = set()
        normal = _style_number(part_style, "minSystemDistance")
        # Every round exports into the working directory. Only the finished PDF goes to
        # ``out_dir``, so nobody sees a half done part there, and a PDF that is open in a
        # viewer meanwhile stops nothing but the last copy.
        while pending:
            # An old file must not pass for the result of a failed export.
            for _, mscz in pending:
                mscz.with_suffix(".pdf").unlink(missing_ok=True)
            job = Path(work) / "job.json"
            job.write_text(
                json.dumps([{"in": str(m), "out": str(m.with_suffix(".pdf"))} for _, m in pending]),
                encoding="utf-8",
            )
            log += _run(["-j", str(job)])
            too_long = []
            for part, mscz in pending:
                pdf = mscz.with_suffix(".pdf")
                if rounds.get(part.name, 0) < ARRANGE_ROUNDS:
                    rounds[part.name] = rounds.get(part.name, 0) + 1
                    if _arrange_marks(pdf, mscz, margin, right, spatium):
                        too_long.append((part, mscz))
                        continue
                part.pages = _page_count(pdf)
                part.beyond_margin = _beyond_margin(pdf, right)
                added = sum(break_before_text(mscz, text) for text in part.beyond_margin)
                if added:
                    part.breaks += added
                    too_long.append((part, mscz))
                    continue
                if part.pages <= MAX_PAGES or part.name in settled:
                    continue
                if part.system_distance not in FALLBACK_DISTANCES:
                    if _systems_on_last_page(pdf, spatium) > OVERFLOW_SYSTEMS:
                        continue
                    distance = FALLBACK_DISTANCES[0]
                elif part.system_distance != FALLBACK_DISTANCES[-1]:
                    step = FALLBACK_DISTANCES.index(part.system_distance) + 1
                    distance = FALLBACK_DISTANCES[step]
                else:
                    # The closer systems did not save the page, so the part keeps its distance.
                    distance = normal
                    settled.add(part.name)
                part.system_distance = distance
                set_system_distance(mscz, distance)
                too_long.append((part, mscz))
            pending = too_long
        for part, mscz in files:
            pdf = mscz.with_suffix(".pdf")
            if pdf.exists():
                shutil.copyfile(pdf, part.output)
            else:
                part.output.unlink(missing_ok=True)
    return PartsResult(source, [part for part, _ in files], log[-2000:], info, margin)


def _extracted_parts(stdout: str) -> list[tuple[str, bytes]]:
    """Names and MuseScore files of the parts that ``--score-parts`` printed as JSON."""
    start = stdout.find("{")
    if start < 0:
        return []
    data = json.loads(stdout[start:])
    return [
        (name, base64.b64decode(blob))
        for name, blob in zip(data.get("parts", []), data.get("partsBin", []), strict=True)
    ]


def _margins(style: Path) -> tuple[float, float]:
    """Left page margin and the right edge of the printable width of ``style``, in points."""
    root = ET.parse(style).getroot()

    def inches(key: str) -> float:
        return float(root.findtext(f"Style/{key}") or 0)

    left = inches("pageOddLeftMargin")
    return left * 72, (left + inches("pagePrintableWidth")) * 72


def _style_number(style: Path, key: str) -> float:
    return float(ET.parse(style).getroot().findtext(f"Style/{key}") or 0)


def _spatium(style: Path) -> float:
    """Staff space of ``style`` in points."""
    return _style_number(style, "spatium") / 25.4 * 72


def _systems_on_last_page(pdf: Path, spatium: float) -> int:
    """Number of systems on the last page of ``pdf``, counted by their staff lines.

    A staff is a group of at least four long horizontal lines a staff space apart. Lines of
    lyrics, ledger lines and hairpins do not form such a group.
    """
    with pymupdf.open(pdf) as doc:
        page = doc[-1]
        heights = sorted(
            {
                round(item[1].y, 1)
                for drawing in page.get_drawings()
                for item in drawing["items"]
                if item[0] == "l"
                and abs(item[1].y - item[2].y) < 0.1
                and abs(item[2].x - item[1].x) > 4 * spatium
            }
        )
    staves: list[list[float]] = []
    for height in heights:
        if staves and height - staves[-1][-1] <= 1.2 * spatium:
            staves[-1].append(height)
        else:
            staves.append([height])
    return sum(1 for lines in staves if len(lines) >= 4)


@dataclass
class _Line:
    text: str
    rect: pymupdf.Rect
    size: float


def _lines(page: pymupdf.Page) -> list[_Line]:
    """Lines of text on ``page`` outside the music font, measured by their glyph outlines."""
    found = []
    for block in page.get_text("dict", flags=pymupdf.TEXT_ACCURATE_BBOXES)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                size = max(span["size"] for span in line["spans"])
                found.append(_Line(text, pymupdf.Rect(line["bbox"]), size))
    return found


def _arrange_marks(pdf: Path, mscz: Path, left: float, right: float, spatium: float) -> int:
    """Move the texts at every rehearsal mark of ``mscz`` beside the mark, as drawn in ``pdf``.

    The texts follow the mark on its right, flush left. Where they would run past ``right``
    they stand before the mark, flush right. Together they are centred on the height of the
    frame of the mark. Returns how many marks got their texts moved,
    leaving out texts already in place.
    """
    if not pdf.exists():
        return 0
    groups = mark_groups(mscz)
    if not groups:
        return 0
    moved = 0
    with pymupdf.open(pdf) as doc:
        pages = [(page, _lines(page)) for page in doc]
        for group in groups:
            shifts = _shifts(group, pages, left, right, spatium)
            if shifts is None or all(
                abs(value) < ARRANGE_TOLERANCE for shift in shifts for value in shift
            ):
                continue
            if place_beside_mark(mscz, group.mark, shifts):
                moved += 1
    return moved


def _shifts(
    group: MarkGroup,
    pages: list[tuple[pymupdf.Page, list[_Line]]],
    left: float,
    right: float,
    spatium: float,
) -> list[tuple[float, float]] | None:
    """Moves sideways and down of the texts of ``group`` in staff spaces, or None.

    None means that the texts do not fit beside the mark on either side.
    """
    marks = [
        (page, line, lines)
        for page, lines in pages
        for line in lines
        if reads_as(line.text, group.mark)
    ]
    if not marks:
        return None
    # A bar number or a playing aid can read like the mark, the mark is the largest of them.
    page, mark, lines = max(marks, key=lambda found: found[1].size)
    # The mark is drawn with a frame around it, which belongs to its width.
    frame = pymupdf.Rect(mark.rect)
    center = (mark.rect.tl + mark.rect.br) / 2
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.contains(center) and rect.width < 4 * mark.rect.height:
            frame |= rect
    texts = []
    for wanted in group.texts:
        # A tempo mark reads with the note symbol in front of the text of the file.
        candidates = [line for line in lines if reads_as(line.text[-len(wanted) :], wanted)]
        if not candidates:
            return None
        texts.append(min(candidates, key=lambda line: _distance(line.rect, frame)))
    # The section titles stand in a row beside the mark. A tempo mark stands above them,
    # flush with the row, where MuseScore stacks it, or in the row when there is no title.
    row = [i for i, tempo in enumerate(group.tempo) if not tempo] or list(range(len(texts)))
    gap = spatium
    targets: dict[int, float] = {}
    x = frame.x1 + gap
    for i in row:
        targets[i] = x
        x += texts[i].rect.width + gap
    row_start, row_end = frame.x1 + gap, x - gap
    if row_end > right:
        x = frame.x0 - gap
        row_end = x
        for i in reversed(row):
            x -= texts[i].rect.width
            targets[i] = x
            x -= gap
        row_start = x + gap
        if row_start < left:
            return None
        for i in range(len(texts)):
            targets.setdefault(i, row_end - texts[i].rect.width)
    else:
        for i in range(len(texts)):
            targets.setdefault(i, row_start)
    # A tempo mark above the row and the row itself, as one block centred on the frame.
    above = [i for i in range(len(texts)) if i not in row]
    rows = [above, row] if above else [row]
    heights = [max(texts[i].rect.height for i in line) for line in rows]
    leading = LINE_GAP * spatium
    top = (frame.y0 + frame.y1) / 2 - (sum(heights) + leading * (len(rows) - 1)) / 2
    tops: dict[int, float] = {}
    for line, height in zip(rows, heights, strict=True):
        for i in line:
            tops[i] = top + (height - texts[i].rect.height)
        top += height + leading
    return [
        ((targets[i] - line.rect.x0) / spatium, (tops[i] - line.rect.y0) / spatium)
        for i, line in enumerate(texts)
    ]


def _distance(rect: pymupdf.Rect, other: pymupdf.Rect) -> float:
    return abs(rect.x0 - other.x0) + abs(rect.y1 - other.y0)


def _beyond_margin(pdf: Path, right: float) -> list[str]:
    """Lines of text in ``pdf`` that end right of ``right``.

    Lines are measured by the outlines of their glyphs. A line is taken as a whole, because
    the PDF splits a text into several pieces where its glyphs are placed apart.
    """
    if not pdf.exists():
        return []
    found: list[str] = []
    with pymupdf.open(pdf) as doc:
        for page in doc:
            blocks = page.get_text("dict", flags=pymupdf.TEXT_ACCURATE_BBOXES)["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if text and line["bbox"][2] > right + MARGIN_TOLERANCE:
                        found.append(text)
    return found


def _page_count(pdf: Path) -> int:
    if not pdf.exists():
        return 0
    with pymupdf.open(pdf) as doc:
        return doc.page_count


def _run(args: list[str]) -> str:
    res = musescore.run(args)
    return res.stdout + res.stderr
