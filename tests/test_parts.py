import base64
import io
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf
import pytest

from xsatz import musescore
from xsatz.parts import (
    FALLBACK_DISTANCES,
    MAX_PAGES,
    default_part_style,
    part_file_name,
    render_parts,
)
from xsatz.render import default_style

DORICO_LIKE = Path(__file__).parent / "fixtures" / "dorico_like.musicxml"
SCORE = (
    '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Score>'
    '<Staff id="1"><Measure/></Staff></Score></museScore>'
)
PART = (
    '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Score>'
    "<Style><spatium>1.75</spatium></Style>"
    '<Staff id="1"><VBox><height>10</height>'
    "<Text><style>title</style><text>Example March</text></Text></VBox>"
    "<Measure/><Measure><voice><SystemText><text>Section</text></SystemText></voice>"
    "</Measure></Staff></Score></museScore>"
)


def _part_file() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Part.mscx", PART)
        archive.writestr("score_style.mss", "<museScore><Style/></museScore>")
    return buffer.getvalue()


# Pages of a fake part at a system distance, and systems on its last page: "Trumpet" fits,
# "Drums" leaves two systems on page 3 that only the last fallback distance saves, "Toms"
# leaves one that none saves, and "Hi-Hat" leaves too many for the fallback.
PAGES = {
    "Trumpet": lambda distance: (2, 6),
    "Drums": lambda distance: (2, 8) if distance <= 8 else (3, 2),
    "Toms": lambda distance: (3, 1),
    "Hi-Hat": lambda distance: (3, 5),
}
# Staff space of the part style in points.
SPATIUM = 1.75 / 25.4 * 72


def _staves(page, count):
    """Draw ``count`` five-line staves, each with an extender line of lyrics under it."""
    for system in range(count):
        top = 100 + system * 80
        for line in range(5):
            y = top + line * SPATIUM
            page.draw_line((50, y), (540, y))
        page.draw_line((100, top + 40), (200, top + 40))


@pytest.fixture
def fake_musescore(monkeypatch):
    """Replace MuseScore by a stand-in that imports, extracts parts and exports jobs."""
    calls: list[list[str]] = []

    def run(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        out = ""
        if "--score-parts" in args:
            names = list(PAGES)
            blob = base64.b64encode(_part_file()).decode("ascii")
            out = "log line\n" + json.dumps({"parts": names, "partsBin": [blob] * len(names)})
        elif "-j" in args:
            for entry in json.loads(Path(args[args.index("-j") + 1]).read_text("utf-8")):
                with zipfile.ZipFile(entry["in"]) as archive:
                    style = ET.fromstring(archive.read("score_style.mss"))
                    title = ET.fromstring(archive.read("Part.mscx")).findtext(
                        ".//Text[style='poet']/text"
                    )
                distance = float(style.findtext("Style/minSystemDistance"))
                pages, last = PAGES[title](distance)
                doc = pymupdf.open()
                for _ in range(pages):
                    doc.new_page()
                _staves(doc[-1], last)
                # Without a system break the section title of the drums runs off the paper.
                with zipfile.ZipFile(entry["in"]) as archive:
                    broken = b"LayoutBreak" in archive.read("Part.mscx")
                if title == "Drums" and not broken:
                    doc[0].insert_text((560, 100), "Section", fontsize=10)
                doc.save(entry["out"])
        else:
            target = Path(args[args.index("-o") + 1])
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("score.mscx", SCORE)
        return subprocess.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(musescore, "run", run)
    return calls


def test_part_file_names_keep_spaces_and_drop_unsafe_characters():
    assert part_file_name("March", "Trumpet 1") == "March - Trumpet 1.pdf"
    assert part_file_name("March", "Trp. 1/2") == "March - Trp. 1_2.pdf"


def test_part_style_ships_with_the_package_and_shares_the_text_font_of_the_score():
    part, score = default_part_style(), default_style()
    assert part.name == "part.mss"
    text = part.read_text(encoding="utf-8")
    assert "<spatium>1.75</spatium>" in text
    assert "<titleFontFace>EB Garamond</titleFontFace>" in text
    assert "<createMultiMeasureRests>1</createMultiMeasureRests>" in text
    assert "<titleFontFace>EB Garamond</titleFontFace>" in score.read_text(encoding="utf-8")


def test_systems_move_closer_only_to_save_a_page_with_one_or_two_systems(tmp_path, fake_musescore):
    before = DORICO_LIKE.read_bytes()

    res = render_parts(DORICO_LIKE, tmp_path)

    assert res.ok
    assert DORICO_LIKE.read_bytes() == before
    by_name = {part.name: part for part in res.parts}
    assert list(by_name) == list(PAGES)
    assert by_name["Trumpet"].output == tmp_path / "dorico_like - Trumpet.pdf"
    pages_and_distance = {name: (p.pages, p.system_distance) for name, p in by_name.items()}
    assert pages_and_distance == {
        "Trumpet": (2, 12),
        "Drums": (2, FALLBACK_DISTANCES[-1]),
        "Toms": (3, 12),
        "Hi-Hat": (3, 12),
    }
    assert by_name["Hi-Hat"].pages > MAX_PAGES
    assert (by_name["Drums"].breaks, by_name["Drums"].beyond_margin) == (1, [])
    assert by_name["Trumpet"].breaks == 0
    # All parts at 12, the drums after their system break with the toms at 10, both one step
    # closer, then the drums at 8 with the toms back at 12. Each export takes every part
    # still in progress.
    exports = [call for call in fake_musescore if "-j" in call]
    assert len(exports) == 4
    assert res.margin == pytest.approx(0.590551 * 72)


def test_parts_are_written_next_to_the_source_by_default(tmp_path, fake_musescore):
    source = tmp_path / "scores" / "march.musicxml"
    source.parent.mkdir()
    source.write_bytes(DORICO_LIKE.read_bytes())

    res = render_parts(source)

    assert {part.output.parent for part in res.parts} == {source.parent}


def _mark_page(x):
    """A page with a framed rehearsal mark at ``x`` and its title and tempo stacked above."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((x, 120), "30", fontsize=18)
    page.draw_circle((x + 10, 114), 12)
    page.insert_text((x, 100), "Own Way", fontsize=10)
    page.insert_text((x, 85), "= 80", fontsize=6)
    return doc, page


@pytest.mark.parametrize(("x", "side"), [(100, "right"), (500, "left")])
def test_title_goes_beside_the_mark_and_the_tempo_above_it(x, side):
    from xsatz.mscz import MarkGroup
    from xsatz.parts import LINE_GAP, _lines, _shifts

    doc, page = _mark_page(x)
    lines = _lines(page)
    by_text = {line.text: line.rect for line in lines}
    spatium = 5.0
    group = MarkGroup("30", ["Own Way", "= 80"], [False, True])

    (title_shift, tempo_shift) = _shifts(group, [(page, lines)], 42, 553, spatium)

    title = by_text["Own Way"] + (title_shift[0] * spatium, title_shift[1] * spatium) * 2
    tempo = by_text["= 80"] + (tempo_shift[0] * spatium, tempo_shift[1] * spatium) * 2
    circle = pymupdf.Rect(x - 2, 102, x + 22, 126)
    if side == "right":
        assert title.x0 == pytest.approx(circle.x1 + spatium, abs=0.5)
        assert tempo.x0 == pytest.approx(title.x0)
    else:
        assert title.x1 == pytest.approx(circle.x0 - spatium, abs=0.5)
        assert tempo.x1 == pytest.approx(title.x1)
    # The tempo stands above the title, and both together are centred on the circle.
    assert title.y0 - tempo.y1 == pytest.approx(LINE_GAP * spatium)
    assert (tempo.y0 + title.y1) / 2 == pytest.approx((circle.y0 + circle.y1) / 2, abs=0.5)
    doc.close()


def test_a_tempo_without_title_goes_beside_the_mark():
    from xsatz.mscz import MarkGroup
    from xsatz.parts import _lines, _shifts

    doc, page = _mark_page(100)
    lines = _lines(page)
    tempo = {line.text: line.rect for line in lines}["= 80"]

    ((right, down),) = _shifts(MarkGroup("30", ["= 80"], [True]), [(page, lines)], 42, 553, 5.0)

    assert tempo.x0 + right * 5.0 == pytest.approx(122 + 5.0, abs=0.5)
    assert (tempo.y0 + tempo.y1) / 2 + down * 5.0 == pytest.approx(114, abs=0.5)
    doc.close()


def test_musescore_files_of_the_parts_are_kept_as_exported(tmp_path, fake_musescore):
    res = render_parts(DORICO_LIKE, tmp_path, mscz=True)

    drums = {part.name: part for part in res.parts}["Drums"]
    assert drums.mscz == tmp_path / "dorico_like - Drums.mscz"
    with zipfile.ZipFile(drums.mscz) as archive:
        style = ET.fromstring(archive.read("score_style.mss"))
        assert b"LayoutBreak" in archive.read("Part.mscx")
    # The file holds the distance and the system break the PDF was exported with.
    assert float(style.findtext("Style/minSystemDistance")) == FALLBACK_DISTANCES[-1]
    assert render_parts(DORICO_LIKE, tmp_path / "plain").parts[0].mscz is None
