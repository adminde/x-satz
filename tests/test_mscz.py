import xml.etree.ElementTree as ET
import zipfile

from xsatz.mscz import add_copyright_frame, shrink_blank_lines

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
