import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from xsatz.prepare import prepare, read_titles

FIXTURE = Path(__file__).parent / "fixtures" / "dorico_like.musicxml"


@pytest.fixture
def prepared(tmp_path):
    target = tmp_path / "prepared.musicxml"
    result = prepare(FIXTURE, target)
    return result, ET.parse(target).getroot()


def test_titles_come_from_the_page_one_credits():
    titles = read_titles(ET.parse(FIXTURE).getroot())
    assert titles.title == "Example March"
    assert titles.label == "Full Score"
    assert titles.lines == ["arr. Somebody", "adapted by Nobody", "for an example band"]
    assert titles.arranger_lines == 1
    assert titles.rights == "© Example Rights"


def test_titles_fall_back_to_the_metadata_without_credits():
    root = ET.parse(FIXTURE).getroot()
    for credit in root.findall("credit"):
        root.remove(credit)
    titles = read_titles(root)
    assert titles.title == "Example March"  # work-title, not the placeholder movement-title
    assert titles.lines == ["adapted by Nobody"]
    assert titles.arranger_lines == 0
    assert titles.rights == "© Example Rights"


def test_credits_are_removed_and_metadata_rewritten(prepared):
    result, root = prepared
    assert result.credits_removed == 7
    assert root.find("credit") is None
    assert root.findtext("work/work-title") == "Example March"
    assert root.findtext("movement-title") == "Example March"
    creators = {c.get("type"): c.text for c in root.findall("identification/creator")}
    assert creators == {
        "composer": "arr. Somebody\n\nadapted by Nobody\nfor an example band",
        "lyricist": "Full Score",
    }
    assert root.findtext("identification/rights") == "© Example Rights"
    assert [c.tag for c in root.find("identification")][-1] == "encoding"


def test_combined_direction_is_split_with_the_rehearsal_mark_first(prepared):
    result, root = prepared
    assert result.directions_split == 1
    directions = root.findall("part/measure/direction")
    kinds = [d.find("direction-type")[0].tag for d in directions]
    assert kinds == ["rehearsal", "words", "metronome"]
    assert all(len(d.findall("direction-type")) == 1 for d in directions)
    assert directions[0].findtext("direction-type/rehearsal") == "1"
    assert directions[0].find("direction-type/rehearsal").get("font-weight") == "bold"
    # The tempo keeps its sound, the texts beside it do not.
    assert [d.find("sound") is not None for d in directions] == [False, False, True]


def test_software_entry_no_longer_names_dorico(prepared):
    result, root = prepared
    assert result.software_replaced == 1
    software = [s.text for s in root.findall("identification/encoding/software")]
    assert len(software) == 1
    assert software[0].startswith("X-Satz")


def test_default_fonts_keep_their_family_but_lose_their_size(prepared):
    result, root = prepared
    assert result.font_sizes_dropped == 2
    fonts = {f.tag: f.attrib for f in root.find("defaults") if f.tag.endswith("-font")}
    assert fonts == {
        "music-font": {"font-family": "Bravura"},
        "word-font": {"font-family": "Academico"},
    }


def test_percussion_kit_gets_one_drum_entry_per_instrument_and_notehead(prepared):
    result, root = prepared
    assert result.kit_entries == 3
    kit = root.find("part-list/score-part[@id='P2']")
    ids = ["P2-X1-x", "P2-X1-circle-x", "P2-X2-normal"]
    assert [i.get("id") for i in kit.findall("score-instrument")] == ids
    assert kit.findtext("score-instrument/instrument-name") == "Hi-Hat (x)"
    midi = kit.findall("midi-instrument")
    assert [m.get("id") for m in midi] == ids
    assert {m.findtext("midi-channel") for m in midi} == {"10"}
    assert len({m.findtext("midi-unpitched") for m in midi}) == 3
    assert [c.tag for c in kit][-6:] == ["score-instrument"] * 3 + ["midi-instrument"] * 3
    notes = root.findall("part[@id='P2']/measure/note")
    assert [n.find("instrument").get("id") for n in notes] == ids
    # Voices, noteheads and positions stay as Dorico wrote them.
    assert [n.findtext("voice") for n in notes] == ["5", "5", "6"]
    assert [n.findtext("notehead") for n in notes] == ["x", "circle-x", None]
    assert [n.findtext("unpitched/display-step") for n in notes] == ["G", "G", "C"]


def test_percussion_keys_are_hidden_and_pitched_keys_kept(prepared):
    result, root = prepared
    assert result.percussion_keys_hidden == 2
    assert root.find("part[@id='P1']/measure/attributes/key").get("print-object") is None
    for part in ("P2", "P3"):
        key = root.find(f"part[@id='{part}']/measure/attributes/key")
        assert key.get("print-object") == "no"
        assert key.findtext("fifths") == "-3"


def test_percussion_without_midi_data_gets_channel_ten(prepared):
    result, root = prepared
    assert result.percussion_channels_added == 1
    timpani = root.find("part-list/score-part[@id='P3']")
    assert [c.tag for c in timpani] == ["part-name", "score-instrument", "midi-instrument"]
    midi = timpani.find("midi-instrument")
    assert midi.get("id") == "P3-X1"
    assert midi.findtext("midi-channel") == "10"
    assert midi.findtext("midi-unpitched") == "37"
    # The positions stay as Dorico wrote them.
    unpitched = root.find("part[@id='P3']/measure/note/unpitched")
    assert (unpitched.findtext("display-step"), unpitched.findtext("display-octave")) == ("E", "4")


def _score(tmp_path, parts):
    """A minimal score with the given (name, percussion) parts."""
    score_parts = "".join(
        f'<score-part id="P{i}"><part-name>{name}</part-name>'
        f"<part-abbreviation>{name[:3]}. (C)</part-abbreviation></score-part>"
        for i, (name, _) in enumerate(parts, 1)
    )
    clef = {True: "<sign>percussion</sign>", False: "<sign>G</sign><line>2</line>"}
    bodies = "".join(
        f'<part id="P{i}"><measure number="1"><attributes><clef>{clef[perc]}</clef></attributes>'
        f"</measure></part>"
        for i, (_, perc) in enumerate(parts, 1)
    )
    path = tmp_path / "band.musicxml"
    score = f"<part-list>{score_parts}</part-list>{bodies}"
    path.write_text(f'<score-partwise version="4.0">{score}</score-partwise>', encoding="utf-8")
    target = tmp_path / "prepared.musicxml"
    result = prepare(path, target)
    return result, ET.parse(target).getroot().find("part-list")


def _layout(part_list):
    """Part list as readable tokens: names, [ and ] with symbol and barline."""
    tokens = []
    for element in part_list:
        if element.tag == "score-part":
            tokens.append(element.findtext("part-name"))
        elif element.get("type") == "start":
            tokens.append(
                f"[{element.findtext('group-symbol')}/{element.findtext('group-barline')}"
            )
        else:
            tokens.append("]")
    return tokens


def test_groups_follow_the_bracketing_of_the_reference(tmp_path):
    result, part_list = _score(
        tmp_path,
        [
            ("Trompete 1 (C)", False),
            ("Trompete 2 (C)", False),
            ("Posaune 1", False),
            ("Posaune 2", False),
            ("Euphonium (C)", False),
            ("Hi-Hat", True),
            ("Pauke", True),
        ],
    )
    assert result.groups_added == 4
    assert _layout(part_list) == [
        "[bracket/no",
        "[square/yes",
        "Trompete 1",
        "Trompete 2",
        "]",
        "[square/yes",
        "Posaune 1",
        "Posaune 2",
        "]",
        "Euphonium",
        "]",
        "[bracket/yes",
        "Hi-Hat",
        "Pauke",
        "]",
    ]


def test_in_c_suffix_is_removed_from_all_names(tmp_path):
    result, part_list = _score(tmp_path, [("Trompete 1 (C)", False), ("Posaune 1", False)])
    names = [p.findtext("part-name") for p in part_list.findall("score-part")]
    abbreviations = [p.findtext("part-abbreviation") for p in part_list.findall("score-part")]
    assert names == ["Trompete 1", "Posaune 1"]
    assert abbreviations == ["Tro.", "Pos."]
    assert result.names_stripped == 3


def test_existing_groups_are_kept(tmp_path):
    source = tmp_path / "grouped.musicxml"
    source.write_text(
        '<score-partwise version="4.0"><part-list>'
        '<part-group type="start" number="1"><group-symbol>brace</group-symbol></part-group>'
        '<score-part id="P1"><part-name>A 1</part-name></score-part>'
        '<score-part id="P2"><part-name>A 2</part-name></score-part>'
        '<part-group type="stop" number="1"/></part-list>'
        '<part id="P1"><measure number="1"/></part><part id="P2"><measure number="1"/></part>'
        "</score-partwise>",
        encoding="utf-8",
    )
    result = prepare(source, tmp_path / "out.musicxml")
    assert result.groups_added == 0


def test_page_layout_comes_from_the_style(tmp_path):
    style = tmp_path / "score.mss"
    style.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Style>'
        "<pageWidth>11.6805</pageWidth><pageHeight>8.25</pageHeight>"
        "<pagePrintableWidth>10.6805</pagePrintableWidth>"
        "<pageOddLeftMargin>0.5</pageOddLeftMargin>"
        "<pageOddTopMargin>0.6</pageOddTopMargin>"
        "<pageOddBottomMargin>0.375</pageOddBottomMargin>"
        "</Style></museScore>",
        encoding="utf-8",
    )
    target = tmp_path / "prepared.musicxml"

    result = prepare(FIXTURE, target, style)

    assert result.page_layout_from_style
    defaults = ET.parse(target).getroot().find("defaults")
    assert [c.tag for c in defaults][:2] == ["scaling", "page-layout"]
    per_inch = 25.4 * 40 / 4.33919  # the scaling of the fixture
    layout = defaults.find("page-layout")
    assert float(layout.findtext("page-height")) == pytest.approx(8.25 * per_inch, abs=0.01)
    margins = layout.find("page-margins")
    assert margins.get("type") == "both"
    expected = {"left": 0.5, "right": 0.5, "top": 0.6, "bottom": 0.375}
    for side, inches in expected.items():
        value = float(margins.findtext(f"{side}-margin"))
        assert value == pytest.approx(inches * per_inch, abs=0.01)


def test_page_layout_stays_without_a_style(prepared):
    result, root = prepared
    assert not result.page_layout_from_style
    assert root.findtext("defaults/page-layout/page-width") == "2734.94"


def test_music_and_playing_aids_are_kept(prepared):
    _, root = prepared
    assert root.findtext("part/measure/note/lyric/text") == "1"
    assert root.find("part/measure/attributes/key/fifths").text == "-3"


def test_original_is_untouched_and_never_overwritten(tmp_path):
    before = FIXTURE.read_bytes()
    prepare(FIXTURE, tmp_path / "copy.musicxml")
    assert FIXTURE.read_bytes() == before
    with pytest.raises(ValueError):
        prepare(FIXTURE, FIXTURE)


def test_prepared_file_declares_musicxml(tmp_path):
    target = tmp_path / "prepared.musicxml"
    prepare(FIXTURE, target)
    head = target.read_text(encoding="utf-8")[:300]
    assert head.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<!DOCTYPE score-partwise" in head


def test_text_font_comes_from_the_style(tmp_path):
    style = tmp_path / "score.mss"
    style.write_text(
        '<museScore version="4.70"><Style><defaultFontFace>Example Serif</defaultFontFace>'
        "</Style></museScore>",
        encoding="utf-8",
    )
    target = tmp_path / "prepared.musicxml"

    result = prepare(FIXTURE, target, style)

    root = ET.parse(target).getroot()
    fonts = {f.tag: f.get("font-family") for f in root.find("defaults") if f.tag.endswith("-font")}
    assert fonts == {
        "music-font": "Bravura",
        "word-font": "Example Serif",
        "lyric-font": "Example Serif",
    }
    assert [e for part in root.findall("part") for e in part.iter() if e.get("font-family")] == []
    assert result.fonts_from_style == 3
