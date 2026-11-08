import xml.etree.ElementTree as ET
from fractions import Fraction

from xsatz.sounds import (
    COUNT_IN_ID,
    HAND_CLAP,
    OPEN_HI_HAT,
    STICKS,
    AudioSettings,
    CountIn,
    PartSound,
    Sound,
    SoundsResult,
    _steps,
    count_in,
    drum_keys,
    first_sound,
    matching,
    part_sounds,
    prepare_sounds,
    tag_unisons,
    transpose_to_sounding,
)

# The transpositions of a band whose brass read in C and play in B flat (ADR 0010).
B_FLAT = {"brass.trumpet": -2, "brass.trombone": -2, "brass.tuba": -14}


def _part(part_id: str, sound: str) -> str:
    return (
        f'<score-part id="{part_id}"><part-name>{part_id}</part-name>'
        f'<score-instrument id="{part_id}-I"><instrument-name>{part_id}</instrument-name>'
        f"<instrument-sound>{sound}</instrument-sound></score-instrument></score-part>"
    )


def _score(parts: str, music: str) -> ET.Element:
    return ET.fromstring(f"<score-partwise><part-list>{parts}</part-list>{music}</score-partwise>")


def _pitched(part_id: str, first: str, transpose: str = "") -> str:
    """A part in 4/4 with ``first`` as the notes of its first bar and a second bar."""
    return (
        f'<part id="{part_id}"><measure number="1"><attributes><divisions>2</divisions>'
        "<time><beats>4</beats><beat-type>4</beat-type></time>"
        f"<clef><sign>G</sign><line>2</line></clef>{transpose}</attributes>{first}</measure>"
        '<measure number="2"><note><pitch><step>C</step><octave>5</octave></pitch>'
        "<duration>8</duration><voice>1</voice><type>whole</type></note></measure></part>"
    )


REST_AND_PICKUP = (
    '<direction><direction-type><words>Intro</words></direction-type><sound tempo="108"/>'
    "</direction>"
    "<note><rest/><duration>7</duration><voice>1</voice></note>"
    "<note><pitch><step>E</step><octave>5</octave></pitch><duration>1</duration>"
    "<voice>1</voice><type>eighth</type></note>"
)
DOWNBEAT = (
    "<note><pitch><step>E</step><octave>5</octave></pitch><duration>8</duration>"
    "<voice>1</voice><type>whole</type></note>"
)


def test_brass_sound_a_whole_tone_lower_and_the_sousaphone_a_ninth():
    octave_down = (
        "<transpose><diatonic>0</diatonic><chromatic>0</chromatic>"
        "<octave-change>-1</octave-change></transpose>"
    )
    root = _score(
        _part("P1", "brass.trumpet.c") + _part("P2", "brass.tuba") + _part("P3", "wind.flute"),
        _pitched("P1", DOWNBEAT) + _pitched("P2", DOWNBEAT, octave_down) + _pitched("P3", DOWNBEAT),
    )

    assert transpose_to_sounding(root, B_FLAT) == ["P1", "P2"]

    trumpet = root.find("part[@id='P1']/measure/attributes/transpose")
    assert (trumpet.findtext("diatonic"), trumpet.findtext("chromatic")) == ("-1", "-2")
    assert trumpet.find("octave-change") is None
    tuba = root.find("part[@id='P2']/measure/attributes/transpose")
    assert [tuba.findtext(t) for t in ("diatonic", "chromatic", "octave-change")] == [
        "-1",
        "-2",
        "-2",
    ]
    assert root.find("part[@id='P3']//transpose") is None


KIT = (
    '<score-part id="P1"><part-name>Kit</part-name>'
    '<score-instrument id="hh"><instrument-name>Hi-Hat (x)</instrument-name>'
    "<instrument-sound>metal.hi-hat</instrument-sound></score-instrument>"
    '<score-instrument id="sn"><instrument-name>Snare (x)</instrument-name>'
    "<instrument-sound>drum.snare-drum</instrument-sound></score-instrument>"
    '<score-instrument id="t1"><instrument-name>Tom 1 (slash)</instrument-name>'
    "<instrument-sound>drum.tom-tom</instrument-sound></score-instrument>"
    '<score-instrument id="t2"><instrument-name>Tom 2 (slash)</instrument-name>'
    "<instrument-sound>drum.tom-tom</instrument-sound></score-instrument>"
    '<score-instrument id="ft"><instrument-name>Floor Tom (normal)</instrument-name>'
    "<instrument-sound>drum.tom-tom</instrument-sound></score-instrument>"
    '<midi-instrument id="hh"><midi-channel>10</midi-channel><midi-unpitched>36</midi-unpitched>'
    "</midi-instrument>"
    '<midi-instrument id="sn"><midi-channel>10</midi-channel><midi-unpitched>37</midi-unpitched>'
    "</midi-instrument>"
    '<midi-instrument id="t1"><midi-channel>10</midi-channel><midi-unpitched>38</midi-unpitched>'
    "</midi-instrument>"
    '<midi-instrument id="t2"><midi-channel>10</midi-channel><midi-unpitched>39</midi-unpitched>'
    "</midi-instrument>"
    '<midi-instrument id="ft"><midi-channel>10</midi-channel><midi-unpitched>40</midi-unpitched>'
    "</midi-instrument></score-part>"
    '<score-part id="P2"><part-name>Bass Drum</part-name>'
    '<score-instrument id="bd"><instrument-name>Bass Drum</instrument-name>'
    "<instrument-sound>drum.kick-drum</instrument-sound></score-instrument>"
    '<midi-instrument id="bd"><midi-channel>10</midi-channel><midi-unpitched>37</midi-unpitched>'
    "</midi-instrument></score-part>"
)


def _hit(instrument: str | None, step: str, octave: int, technical: str = "") -> str:
    ref = f'<instrument id="{instrument}"/>' if instrument else ""
    marks = f"<notations><technical>{technical}</technical></notations>" if technical else ""
    return (
        f"<note><unpitched><display-step>{step}</display-step>"
        f"<display-octave>{octave}</display-octave></unpitched><duration>1</duration>"
        f"{ref}<voice>1</voice>{marks}</note>"
    )


def _percussion(part_id: str, notes: str) -> str:
    return (
        f'<part id="{part_id}"><measure number="1"><attributes><divisions>1</divisions>'
        f"<clef><sign>percussion</sign></clef></attributes>{notes}</measure></part>"
    )


def _keys(root: ET.Element) -> dict[str, int]:
    return {
        m.get("id"): int(m.findtext("midi-unpitched")) - 1 for m in root.iter("midi-instrument")
    }


def test_percussion_entries_get_general_midi_keys():
    kit = (
        _hit("hh", "G", 5)
        + _hit("hh", "G", 5, "<open/>")
        + _hit("hh", "G", 5, '<other-technical smufl="pictHalfOpen1"/>')
        + _hit("sn", "C", 5)
        + _hit("t1", "B", 4)
        + _hit("t2", "E", 5)
        + _hit("ft", "G", 4)
    )
    root = _score(KIT, _percussion("P1", kit) + _percussion("P2", _hit(None, "E", 4)))
    result = SoundsResult()

    drum_keys(root, result)

    keys = _keys(root)
    assert keys["hh"] == 42
    assert keys["hh-open"] == OPEN_HI_HAT
    assert keys["sn"] == 37
    # The higher tom on the staff gets the higher key.
    assert (keys["t2"], keys["t1"], keys["ft"]) == (48, 45, 43)
    assert keys["bd"] == 36
    assert result.open_hi_hats == 2
    ids = [n.find("instrument").get("id") for n in root.find("part[@id='P1']").iter("note")]
    assert ids[:3] == ["hh", "hh-open", "hh-open"]
    # A single instrument names itself on its notes, after the duration.
    bass = root.find("part[@id='P2']/measure/note")
    assert [c.tag for c in bass][:3] == ["unpitched", "duration", "instrument"]
    assert result.unmapped == []


def test_an_instrument_without_sound_claps_and_an_unknown_one_is_reported():
    parts = (
        '<score-part id="P1"><part-name>Body</part-name>'
        '<score-instrument id="b"><instrument-name>Body</instrument-name></score-instrument>'
        '<midi-instrument id="b"><midi-channel>10</midi-channel>'
        "<midi-unpitched>37</midi-unpitched></midi-instrument></score-part>"
        '<score-part id="P2"><part-name>Gong</part-name>'
        '<score-instrument id="g"><instrument-name>Gong</instrument-name>'
        "<instrument-sound>metal.gong</instrument-sound></score-instrument>"
        '<midi-instrument id="g"><midi-channel>10</midi-channel>'
        "<midi-unpitched>37</midi-unpitched></midi-instrument></score-part>"
    )
    root = _score(
        parts, _percussion("P1", _hit(None, "E", 4)) + _percussion("P2", _hit(None, "E", 4))
    )
    result = SoundsResult()

    drum_keys(root, result)

    assert _keys(root)["b"] == HAND_CLAP
    assert result.unmapped == ["Gong"]


def _clicks(root: ET.Element) -> list[list[int]]:
    part = root.find(f"part[@id='{COUNT_IN_ID}']")
    return [
        [int(n.findtext("duration")) for n in m.findall("note") if n.find("unpitched") is not None]
        for m in part.findall("measure")
    ]


def test_a_pickup_gets_one_bar_of_count_in_and_clicks_up_to_the_first_note():
    root = _score(_part("P1", "brass.trumpet.c"), _pitched("P1", REST_AND_PICKUP))
    result = SoundsResult()

    assert first_sound(root) == Fraction(7, 2)
    count_in(root, result, CountIn())

    measures = root.find("part[@id='P1']").findall("measure")
    assert [(m.get("number"), m.get("implicit")) for m in measures] == [
        ("0", "yes"),
        ("1", None),
        ("2", None),
    ]
    assert measures[0].find("sound").get("tempo") == "108"
    assert measures[0].find("attributes/time/beats").text == "4"
    # "1 - 2 -" in halves, then "1 2 3 4" in quarters before the pickup on 4+.
    assert _clicks(root) == [[4, 4], [2, 2, 2, 2], []]
    assert (result.count_in_bars, result.count_in_clicks) == (1, 6)
    loud = root.find(f"part[@id='{COUNT_IN_ID}']/measure/direction/direction-type/dynamics")
    assert loud is not None and loud.find("f") is not None
    keys = _keys(root)
    assert keys[f"{COUNT_IN_ID}-I"] == STICKS
    assert root.find(f"part-list/score-part[@id='{COUNT_IN_ID}']") is not None


def test_music_on_the_first_beat_gets_two_bars_of_count_in():
    root = _score(_part("P1", "brass.trumpet.c"), _pitched("P1", DOWNBEAT))
    result = SoundsResult()

    count_in(root, result, CountIn(key=76, dynamic="ff"))

    numbers = [m.get("number") for m in root.find("part[@id='P1']").findall("measure")]
    assert numbers == ["-1", "0", "1", "2"]
    assert _clicks(root) == [[4, 4], [2, 2, 2, 2], [], []]
    assert result.count_in_bars == 2
    assert _keys(root)[f"{COUNT_IN_ID}-I"] == 76
    loud = root.find(f"part[@id='{COUNT_IN_ID}']/measure/direction/direction-type/dynamics")
    assert loud.find("ff") is not None


def test_prepare_sounds_runs_every_step():
    root = _score(_part("P1", "brass.trombone"), _pitched("P1", REST_AND_PICKUP))

    result = prepare_sounds(root, AudioSettings(transpose=B_FLAT, count_in=CountIn()))

    assert result.transposed == ["P1"]
    assert result.count_in_clicks == 6


def test_by_default_the_score_plays_as_written_with_general_midi_drums():
    root = _score(
        _part("P0", "brass.trumpet.c") + KIT,
        _pitched("P0", REST_AND_PICKUP)
        + _percussion("P1", _hit("hh", "G", 5))
        + _percussion("P2", _hit(None, "E", 4)),
    )

    result = prepare_sounds(root, AudioSettings())

    assert result.transposed == []
    assert root.find("part[@id='P0']//transpose") is None
    assert (_keys(root)["hh"], _keys(root)["bd"]) == (42, 36)
    assert root.find(f"part[@id='{COUNT_IN_ID}']") is None
    assert result.count_in_bars == 0


def test_semitones_become_diatonic_and_chromatic_steps_and_octaves():
    assert _steps(-2) == (-1, -2, 0)
    assert _steps(-14) == (-1, -2, -1)
    assert _steps(-12) == (0, 0, -1)
    assert _steps(7) == (4, 7, 0)


def test_the_longest_matching_instrument_sound_wins():
    table = {"brass": 1, "brass.trumpet": 2}
    assert matching(table, "brass.trumpet.c") == 2
    assert matching(table, "brass.tuba") == 1
    assert matching(table, "wind.flute") is None


def _melody(part_id: str, notes: str, transpose: str = "") -> str:
    return (
        f'<part id="{part_id}"><measure number="1"><attributes><divisions>1</divisions>'
        "<time><beats>4</beats><beat-type>4</beat-type></time>"
        f"<clef><sign>G</sign><line>2</line></clef>{transpose}</attributes>{notes}</measure>"
        "</part>"
    )


def _n(step: str, octave: int, duration: int = 1, tie: str = "") -> str:
    ties = "".join(f'<tie type="{t}"/>' for t in tie.split()) if tie else ""
    return (
        f"<note><pitch><step>{step}</step><octave>{octave}</octave></pitch>"
        f"<duration>{duration}</duration>{ties}<voice>1</voice></note>"
    )


def _colours(root: ET.Element, part_id: str) -> list[str | None]:
    return [n.get("color") for n in root.find(f"part[@id='{part_id}']").iter("note")]


def test_unisons_of_parts_with_the_same_samples_are_tagged_by_group():
    octave_down = (
        "<transpose><diatonic>0</diatonic><chromatic>0</chromatic>"
        "<octave-change>-1</octave-change></transpose>"
    )
    root = _score(
        _part("P1", "brass.trumpet")
        + _part("P2", "brass.trumpet")
        + _part("P3", "brass.trumpet")
        + _part("P4", "brass.trombone"),
        # P2 shares C and the tied E with P1, P3 sounds C an octave lower, P4 has other samples.
        _melody("P1", _n("C", 5) + _n("D", 5) + _n("E", 5, 1, "start") + _n("E", 5, 1, "stop"))
        + _melody("P2", _n("C", 5) + _n("F", 5) + _n("E", 5, 2))
        + _melody("P3", _n("C", 6) + _n("D", 5, 2) + _n("E", 5), octave_down)
        + _melody("P4", _n("C", 5) + _n("D", 5) + _n("E", 5, 2)),
    )

    assert tag_unisons(root, [None] * 4) == 2

    # C is one group, the tied E against the half note E is the second. D differs in length,
    # P3's C sounds an octave lower than written, and P4 has samples of its own.
    assert _colours(root, "P1") == ["#000001", None, "#000002", "#000002"]
    assert _colours(root, "P2") == ["#000001", None, "#000002"]
    assert _colours(root, "P3") == ["#000001", None, None]
    assert _colours(root, "P4") == [None, None, None]


def test_parts_with_different_sounds_of_the_settings_are_no_unison():
    root = _score(
        _part("P1", "brass.trumpet.c") + _part("P2", "brass.trumpet.bflat"),
        _melody("P1", _n("C", 5)) + _melody("P2", _n("C", 5)),
    )

    assert tag_unisons(root, [Sound("A", 0, 1), Sound("A", 0, 2)]) == 0
    assert tag_unisons(root, [Sound("A", 0, 1), Sound("A", 0, 1)]) == 1


def test_a_part_changes_the_sound_of_its_instrument_by_name():
    root = _score(
        _part("P1", "brass.trumpet.c") + _part("P2", "brass.trumpet.c") + _part("P3", "wind.flute"),
        _melody("P1", _n("C", 5)) + _melody("P2", _n("C", 5)) + _melody("P3", _n("C", 5)),
    )
    settings = AudioSettings(
        sounds={"brass.trumpet": Sound("Orchestra", 0, 27)},
        parts={"P2": PartSound(program=28), "P3": PartSound(bank=1)},
    )

    assert part_sounds(root, settings) == [
        Sound("Orchestra", 0, 27),
        Sound("Orchestra", 0, 28),
        # A part without a sound of its instrument starts from MuseScore's own SoundFont.
        Sound("MS Basic", 1, None),
    ]
