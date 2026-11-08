import array
import math
import struct

from xsatz.soundfont import Shaping, shape

RATE = 1000


def _chunk(tag: bytes, body: bytes) -> bytes:
    return tag + struct.pack("<I", len(body)) + body + (b"\0" if len(body) % 2 else b"")


def _list(kind: bytes, *chunks: bytes) -> bytes:
    return _chunk(b"LIST", kind + b"".join(chunks))


def _swelling(length: int, rise: int) -> array.array:
    """A 50 Hz tone that grows over ``rise`` sample points to full level."""
    return array.array(
        "h",
        (
            int(30000 * min(1, i / rise) * math.sin(2 * math.pi * 50 * i / RATE))
            for i in range(length)
        ),
    )


def sf2(presets: list[tuple[int, int, int]], samples: list[array.array]) -> bytes:
    """A SoundFont with one instrument per preset (bank, program, attack in timecents).

    Instrument n plays sample n, a left sample linked to the next one when there are two.
    """
    pcm = b"".join(s.tobytes() + b"\0" * 92 for s in samples)
    phdr, pbag, pgen, inst, ibag, igen = b"", b"", b"", b"", b"", b""
    for n, (bank, program, attack) in enumerate(presets):
        phdr += struct.pack("<20sHHHIII", f"P{n}".encode(), program, bank, n, 0, 0, 0)
        pbag += struct.pack("<HH", n, 0)
        pgen += struct.pack("<HH", 41, n)
        inst += struct.pack("<20sH", f"I{n}".encode(), n)
        ibag += struct.pack("<HH", 2 * n, 0)
        igen += struct.pack("<Hh", 34, attack) + struct.pack("<HH", 53, n)
    count = len(presets)
    phdr += struct.pack("<20sHHHIII", b"EOP", 0, 0, count, 0, 0, 0)
    pbag += struct.pack("<HH", count, 0)
    pgen += struct.pack("<HH", 0, 0)
    inst += struct.pack("<20sH", b"EOI", count)
    ibag += struct.pack("<HH", 2 * count, 0)
    igen += struct.pack("<HH", 0, 0)
    shdr, start = b"", 0
    for n, s in enumerate(samples):
        stereo = len(samples) == 2
        link, kind = (1 - n, 4 if n == 0 else 2) if stereo else (0, 1)
        shdr += struct.pack(
            "<20sIIIIIBbHH",
            f"S{n}".encode(),
            start,
            start + len(s),
            start,
            start + len(s),
            RATE,
            60,
            0,
            link,
            kind,
        )
        start += len(s) + 46
    shdr += struct.pack("<20sIIIIIBbHH", b"EOS", 0, 0, 0, 0, 0, 0, 0, 0, 0)
    pdta = _list(
        b"pdta",
        _chunk(b"phdr", phdr),
        _chunk(b"pbag", pbag),
        _chunk(b"pmod", b"\0" * 10),
        _chunk(b"pgen", pgen),
        _chunk(b"inst", inst),
        _chunk(b"ibag", ibag),
        _chunk(b"imod", b"\0" * 10),
        _chunk(b"igen", igen),
        _chunk(b"shdr", shdr),
    )
    body = (
        b"sfbk"
        + _list(b"INFO", _chunk(b"ifil", struct.pack("<HH", 2, 1)))
        + _list(b"sdta", _chunk(b"smpl", pcm))
        + pdta
    )
    return _chunk(b"RIFF", body)


def _headers(data: bytes) -> list[tuple]:
    i = data.find(b"shdr")
    size = struct.unpack("<I", data[i + 4 : i + 8])[0]
    return [
        struct.unpack("<20sIIIIIBbHH", data[i + 8 + k : i + 54 + k]) for k in range(0, size, 46)
    ]


def _attacks(data: bytes) -> list[int]:
    i = data.find(b"igen")
    size = struct.unpack("<I", data[i + 4 : i + 8])[0]
    gens = [struct.unpack("<Hh", data[i + 8 + k : i + 12 + k]) for k in range(0, size, 4)]
    return [amount for oper, amount in gens if oper == 34]


def test_shaping_starts_a_swelling_sample_where_it_reaches_half_its_level(tmp_path):
    source, target = tmp_path / "Font.sf2", tmp_path / "Font-swell50.sf2"
    source.write_bytes(sf2([(0, 27, -12000)], [_swelling(1000, 400)]))

    result = shape(Shaping(source, swell=0.5), target)

    assert result.samples_cut == 1 and target.stat().st_size == source.stat().st_size
    original, shaped = _headers(source.read_bytes())[0], _headers(target.read_bytes())[0]
    cut = shaped[1] - original[1]
    # Half the level comes after 200 of 400 points, the start lies at a zero crossing before.
    assert 180 <= cut <= 200
    assert shaped[2] == original[2] and shaped[3] == shaped[1]


def test_linked_stereo_samples_are_cut_alike(tmp_path):
    source, target = tmp_path / "Font.sf2", tmp_path / "copy.sf2"
    source.write_bytes(sf2([(0, 27, -12000)], [_swelling(1000, 400), _swelling(1000, 100)]))

    shape(Shaping(source, swell=0.5), target, {(0, 27)})

    before, after = _headers(source.read_bytes()), _headers(target.read_bytes())
    assert after[0][1] - before[0][1] == after[1][1] - before[1][1] > 0


def test_a_cut_never_takes_more_than_the_limit(tmp_path):
    source, target = tmp_path / "Font.sf2", tmp_path / "copy.sf2"
    source.write_bytes(sf2([(0, 27, -12000)], [_swelling(1000, 1000)]))

    shape(Shaping(source, swell=0.9), target)

    assert _headers(target.read_bytes())[0][1] - _headers(source.read_bytes())[0][1] <= 400


def test_fade_in_shortens_long_attacks_of_the_chosen_presets_only(tmp_path):
    source, target = tmp_path / "Font.sf2", tmp_path / "copy.sf2"
    slow, quick = 1200 * math.log2(0.6), -12000
    source.write_bytes(
        sf2([(0, 29, round(slow)), (0, 30, round(slow)), (0, 31, quick)], [_swelling(100, 10)] * 3)
    )

    result = shape(Shaping(source, fade_in=0.01), target, {(0, 29), (0, 31)})

    assert result.fades_shortened == 1
    assert _attacks(target.read_bytes()) == [round(1200 * math.log2(0.01)), round(slow), quick]


def test_the_copy_is_named_after_the_original_and_its_shaping(tmp_path):
    assert Shaping(tmp_path / "Font.sf2", 0.5, 0.01).name() == "Font-swell50-fade10ms"
    assert Shaping(tmp_path / "Font.sf2", fade_in=0.01).name() == "Font-fade10ms"
