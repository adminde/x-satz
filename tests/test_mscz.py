import xml.etree.ElementTree as ET
import zipfile

import pytest

from xsatz.mscz import (
    add_copyright_frame,
    break_before_text,
    edit_part,
    mark_groups,
    place_beside_mark,
    reads_as,
    set_system_distance,
    shrink_blank_lines,
    system_distance,
)

MEASURE = "<Measure><voice><Rest><durationType>measure</durationType></Rest></voice></Measure>"
BREAK = "<LayoutBreak><subtype>page</subtype></LayoutBreak>"


def _mscz(path, staff_content):
    """A MuseScore file with an instrument staff in the parts and one music staff."""
    mscx = (
        '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Score>'
        '<Part id="1"><Staff id="1"><StaffType group="pitched"/></Staff></Part>'
        f'<Staff id="1">{staff_content}</Staff></Score></museScore>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("score.mscx", mscx)
        archive.writestr("score_style.mss", "<museScore/>")
    return path


def _staff(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("score.mscx"))
        assert archive.read("score_style.mss") == b"<museScore/>"
    return root.find("Score/Staff[@id='1']")


def test_frame_follows_the_first_system_and_takes_its_page_break(tmp_path):
    first_page_end = MEASURE.replace("<voice>", BREAK + "<voice>")
    second_page_end = first_page_end
    path = _mscz(tmp_path / "score.mscz", MEASURE + first_page_end + MEASURE + second_page_end)

    assert add_copyright_frame(path, "© Example & Co")

    staff = _staff(path)
    assert [e.tag for e in staff] == ["Measure", "Measure", "VBox", "Measure", "Measure"]
    frame = staff[2]
    assert frame.findtext("Text/style") == "copyright"
    assert frame.findtext("Text/text") == "© Example & Co"
    assert frame.findtext("LayoutBreak/subtype") == "page"
    # The break moved into the frame, the second page keeps its own break.
    assert staff[1].find(".//LayoutBreak") is None
    assert staff[4].find(".//LayoutBreak") is not None


def test_single_page_score_gets_the_frame_at_the_end(tmp_path):
    path = _mscz(tmp_path / "score.mscz", MEASURE + MEASURE)

    assert add_copyright_frame(path, "© Example")

    staff = _staff(path)
    assert [e.tag for e in staff] == ["Measure", "Measure", "VBox"]
    assert staff[2].find("LayoutBreak") is None


def test_empty_lines_of_the_credit_block_get_half_the_font_size(tmp_path):
    path = tmp_path / "score.mscz"
    mscx = (
        '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Score><VBox>'
        "<Text><style>composer</style><text>arr. A<br/><br/>adapted by B<br/>for C</text></Text>"
        "<Text><style>title</style><text>T<br/><br/>U</text></Text>"
        f'</VBox><Staff id="1">{MEASURE}</Staff></Score></museScore>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("score.mscx", mscx)
        archive.writestr(
            "score_style.mss",
            "<museScore><Style><composerFontSize>8.5</composerFontSize></Style></museScore>",
        )

    assert shrink_blank_lines(path) == 1

    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("score.mscx"))
    composer, title = root.iter("text")
    assert composer.text == "arr. A"
    assert [(e.tag, e.get("size"), e.tail) for e in composer] == [
        ("br", None, None),
        ("font", "4.25", " "),
        ("br", None, None),
        ("font", "8.5", "adapted by B"),
        ("br", None, "for C"),
    ]
    assert [e.tag for e in title] == ["br", "br"]  # other styles stay as they are


def test_no_frame_without_text(tmp_path):
    path = _mscz(tmp_path / "score.mscz", MEASURE)
    before = path.read_bytes()

    assert not add_copyright_frame(path, "")
    assert path.read_bytes() == before


PART_STYLE = (
    '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Style>'
    "<titleFontSize>24</titleFontSize><composerFontSize>8.5</composerFontSize>"
    "<spatium>1.75</spatium><minSystemDistance>8.5</minSystemDistance>"
    "<minSystemSpread>8.5</minSystemSpread></Style></museScore>"
)


def _part(path, frame):
    """A part as MuseScore extracts it, with a style of its own inside the score entry."""
    mscx = (
        '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Score>'
        "<Style><spatium>1.75</spatium><showFooter>0</showFooter></Style>"
        f'<Staff id="1">{frame}{MEASURE}</Staff></Score></museScore>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Part.mscx", mscx)
        archive.writestr("score_style.mss", "<museScore><Style/></museScore>")
    return path


def _read_part(path):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("Part.mscx")), archive.read("score_style.mss")


TITLE_FRAME = (
    "<VBox><height>10</height>"
    "<Text><style>title</style><text>Example March</text></Text>"
    "<Text><style>composer</style><text>arr. Somebody<br/>"
    '<font size="4.25"/> <br/><font size="8.5"/>adapted by Nobody</text></Text>'
    "<Text><style>poet</style><text>Full Score</text></Text>"
    "<Text><style>instrument_excerpt</style><text>Trumpet 1</text></Text>"
    "</VBox>"
)


def test_part_gets_the_part_style_and_its_name_in_the_title_block(tmp_path):
    style = tmp_path / "part.mss"
    style.write_text(PART_STYLE, encoding="utf-8")
    path = _part(tmp_path / "part.mscz", TITLE_FRAME)

    edit_part(path, "Trumpet 1", style)

    root, style_data = _read_part(path)
    assert style_data == style.read_bytes()
    assert root.find("Score/Style") is None
    frame = root.find("Score/Staff/VBox")
    styles = [t.findtext("style") for t in frame.findall("Text")]
    assert "instrument_excerpt" not in styles
    assert frame.findtext("Text[style='poet']/text") == "Trumpet 1"
    # Title and two and a half lines of credits at 1.2 times their size, plus the gap.
    points = 1.2 * (24 + 2.5 * 8.5)
    assert float(frame.findtext("height")) == pytest.approx(
        points / 72 * 25.4 / 1.75 + 0.5, abs=0.05
    )


def test_part_without_label_gets_one(tmp_path):
    style = tmp_path / "part.mss"
    style.write_text(PART_STYLE, encoding="utf-8")
    frame = "<VBox><height>30</height><Text><style>title</style><text>T</text></Text></VBox>"
    path = _part(tmp_path / "part.mscz", frame)

    edit_part(path, "Drums", style)

    root, _ = _read_part(path)
    assert root.findtext("Score/Staff/VBox/Text[style='poet']/text") == "Drums"
    # A frame that is already tall enough keeps its height.
    assert root.findtext("Score/Staff/VBox/height") == "30"


def test_system_distance_is_set_for_both_layouts(tmp_path):
    style = tmp_path / "part.mss"
    style.write_text(PART_STYLE, encoding="utf-8")
    path = _part(tmp_path / "part.mscz", TITLE_FRAME)
    edit_part(path, "Trumpet 1", style)
    assert system_distance(path) == 8.5

    set_system_distance(path, 6.5)

    _, style_data = _read_part(path)
    root = ET.fromstring(style_data)
    for key in ("minSystemDistance", "maxSystemDistance", "minSystemSpread", "maxSystemSpread"):
        assert root.findtext(f"Style/{key}") == "6.5"
    assert system_distance(path) == 6.5


SECTION = (
    "<Measure><eid>m3</eid><voice><RehearsalMark><text>44</text></RehearsalMark>"
    "<SystemText><text>Stick Together</text></SystemText></voice></Measure>"
)
MM_REST = "<Measure><multiMeasureRest>6</multiMeasureRest><voice/></Measure>"


def test_break_moves_a_text_at_the_margin_to_the_next_system(tmp_path):
    first, second = MEASURE, "<Measure><eid>m2</eid><voice/></Measure>"
    path = _mscz(tmp_path / "part.mscz", first + second + SECTION + MM_REST)

    assert break_before_text(path, "Stick Together")

    measures = _staff(path).findall("Measure")
    assert measures[0].find("LayoutBreak") is None
    assert [e.tag for e in measures[1]][:2] == ["eid", "LayoutBreak"]
    assert measures[1].findtext("LayoutBreak/subtype") == "line"
    # A second call finds the break in place and adds none.
    assert not break_before_text(path, "Stick Together")


def test_break_finds_a_text_cut_at_the_edge_of_the_paper(tmp_path):
    path = _mscz(tmp_path / "part.mscz", MEASURE + SECTION)

    assert break_before_text(path, "Stick Tog")
    assert _staff(path).findall("Measure")[0].find("LayoutBreak") is not None


def test_no_break_for_unknown_texts_short_beginnings_or_the_first_measure(tmp_path):
    path = _mscz(tmp_path / "part.mscz", SECTION + MEASURE)

    assert not break_before_text(path, "Unknown")
    assert not break_before_text(path, "4")
    assert not break_before_text(path, "Stick Together")


MARK_STYLE = (
    '<museScore version="4.70"><Style><rehearsalMarkPosAbove x="0" y="-5"/>'
    '<systemTextPosAbove x="0" y="-2"/><tempoPosAbove x="0" y="-2"/></Style></museScore>'
)
MARKED = (
    "<Measure><voice><RehearsalMark><text>30</text></RehearsalMark>"
    "<SystemText><text>Own Way</text></SystemText>"
    "<Tempo><tempo>1.3</tempo><text><sym>metNoteQuarterUp</sym> = 80</text></Tempo>"
    "</voice></Measure>"
)
LONELY_MARK = "<Measure><voice><RehearsalMark><text>44</text></RehearsalMark></voice></Measure>"


def _marked(path):
    path = _mscz(path, MARKED + LONELY_MARK)
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries["score_style.mss"] = MARK_STYLE.encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_mark_groups_list_the_texts_at_each_rehearsal_mark(tmp_path):
    path = _marked(tmp_path / "part.mscz")

    (group,) = mark_groups(path)

    assert group.mark == "30"
    assert group.texts == ["Own Way", "= 80"]
    assert group.tempo == [False, True]


def test_texts_start_on_the_height_of_the_mark_and_then_move_by_their_shifts(tmp_path):
    path = _marked(tmp_path / "part.mscz")

    assert place_beside_mark(path, "30", [(3.0, 1.0), (12.5, 1.0)])
    assert place_beside_mark(path, "30", [(0.5, 1.5), (-0.5, -1.0)])

    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("score.mscx"))
    title = root.find(".//SystemText/offset")
    tempo = root.find(".//Tempo/offset")
    # The first call puts both on the height of the mark, the second moves them from there.
    assert (float(title.get("x")), float(title.get("y"))) == (3.5, -3.5)
    assert (float(tempo.get("x")), float(tempo.get("y"))) == (12.0, -6.0)
    assert not place_beside_mark(path, "99", [(1.0, 0.0), (1.0, 0.0)])


def test_part_texts_lose_their_own_font_family(tmp_path):
    style = tmp_path / "part.mss"
    style.write_text(PART_STYLE, encoding="utf-8")
    tempo = (
        "<Measure><voice><Tempo><text><sym>metNoteQuarterUp</sym>"
        '<font face="Academico"/> = 80<font face="Other" size="9"/>!</text></Tempo>'
        "</voice></Measure>"
    )
    path = _part(tmp_path / "part.mscz", TITLE_FRAME + tempo)

    edit_part(path, "Trumpet 1", style)

    root, _ = _read_part(path)
    text = root.find(".//Tempo/text")
    assert ET.tostring(text, encoding="unicode") == (
        '<text><sym>metNoteQuarterUp</sym> = 80<font size="9" />!</text>'
    )


def test_an_unreadable_glyph_in_a_pdf_text_stands_for_any_character(tmp_path):
    assert reads_as("Status �uo", "Status Quo")
    assert not reads_as("Status Duo", "Status Quo")
    assert not reads_as("Status �uo!", "Status Quo")
    path = _mscz(tmp_path / "part.mscz", MEASURE + SECTION.replace("Stick Together", "Quick"))

    assert break_before_text(path, "�uick")
