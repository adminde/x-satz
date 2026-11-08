import array
import json
import math
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from xsatz import musescore
from xsatz.audio import render_audio, scale_velocities, track_count, wav_peak
from xsatz.sounds import COUNT_IN_ID, AudioSettings, CountIn, Sound

DORICO_LIKE = Path(__file__).parent / "fixtures" / "dorico_like.musicxml"


def _track(*events: bytes) -> bytes:
    body = b"".join(events) + b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _midi(tracks: int) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, 1, tracks, 480)
    # A name, a note on and, with running status, a second note on and a note off.
    track = _track(
        b"\x00\xff\x03\x04Horn",
        b"\x00\x90\x3c\x50",
        b"\x60\x3e\x64",
        b"\x60\x3c\x00",
    )
    return header + track * tracks


def _wav(samples: list[float], kind: int) -> bytes:
    """A mono WAV of ``samples``, 16 bit PCM for kind 1 and 32 bit float for kind 3."""
    if kind == 3:
        body, width = array.array("f", samples).tobytes(), 4
    else:
        body, width = array.array("h", (int(x * 32767) for x in samples)).tobytes(), 2
    fmt = struct.pack("<HHIIHH", kind, 1, 44100, 44100 * width, width, 8 * width)
    chunks = (
        b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(body)) + body
    )
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def _velocities(data: bytes) -> list[list[int]]:
    out = []
    position = 14
    while position < len(data):
        length = struct.unpack(">I", data[position + 4 : position + 8])[0]
        body = data[position + 8 : position + 8 + length]
        out.append([body[11], body[14], body[18]])
        position += 8 + length
    return out


def test_scale_velocities_changes_only_the_given_tracks():
    data = _midi(3)

    scaled = scale_velocities(data, {0, 2}, 0.5)

    assert len(scaled) == len(data)
    assert track_count(scaled) == 3
    # Note off (velocity 0) stays 0, the running status note is scaled as well.
    assert _velocities(scaled) == [[40, 50, 0], [80, 100, 0], [40, 50, 0]]


def test_scale_velocities_keeps_at_least_one():
    assert _velocities(scale_velocities(_midi(1), {0}, 0.001)) == [[1, 1, 0]]


def test_scale_velocities_refuses_other_files():
    with pytest.raises(ValueError):
        scale_velocities(b"RIFF", {0}, 0.5)


@pytest.fixture
def fake_musescore(monkeypatch):
    """Replace MuseScore by one that imports, writes MIDIs and records every MP3 export.

    An import writes a MuseScore file with one part per part of the MusicXML. A MIDI gets
    one track per part. An MP3 export records the mixer of the file it is given.
    """
    seen: dict = {"musicxml": [], "mp3": [], "peak": 0.5}

    def parts_of(path: Path) -> int:
        if path.suffix == ".mscz":
            with zipfile.ZipFile(path) as archive:
                return archive.read("score.mscx").decode().count("<Part ")
        root = ET.parse(path).getroot()
        seen["musicxml"].append(root)
        return len(root.findall("part"))

    def run(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
        target, source = Path(args[args.index("-o") + 1]), Path(args[-1])
        if target.suffix == ".mscz":
            parts = "".join(
                f'<Part id="{n + 1}"><Instrument id="i{n + 1}"/></Part>'
                for n in range(parts_of(source))
            )
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("score.mscx", f"<museScore><Score>{parts}</Score></museScore>")
                archive.writestr("audiosettings.json", '{"tracks": []}')
        elif target.suffix == ".mid":
            target.write_bytes(_midi(parts_of(source)))
        elif target.suffix == ".wav":
            target.write_bytes(_wav([0.1, -seen["peak"], 0.2], 3))
        else:
            with zipfile.ZipFile(source) as archive:
                seen["mp3"].append((target.name, json.loads(archive.read("audiosettings.json"))))
            target.write_bytes(b"mp3")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(musescore, "run", run)
    return seen


def test_render_audio_writes_an_mp3_of_the_band_and_one_per_part(tmp_path, fake_musescore):
    before = DORICO_LIKE.read_bytes()

    res = render_audio(DORICO_LIKE, tmp_path, AudioSettings(count_in=CountIn()))

    assert res.ok
    assert res.full == tmp_path / "dorico_like.mp3"
    assert [p.name for p in res.practice] == ["Trombone", "Drum Kit", "Timpani"]
    assert [p.mp3.name for p in res.practice] == [
        "dorico_like - Trombone.mp3",
        "dorico_like - Drum Kit.mp3",
        "dorico_like - Timpani.mp3",
    ]
    # Without --midi no MIDI is written.
    assert res.full_midi is None and all(p.midi is None for p in res.practice)
    assert not list(tmp_path.glob("*.mid"))
    # MuseScore reads the sounding copy with its count-in, the original stays as it was.
    assert fake_musescore["musicxml"][0].find(f"part[@id='{COUNT_IN_ID}']") is not None
    assert DORICO_LIKE.read_bytes() == before


def test_render_audio_plays_the_score_as_written_by_default(tmp_path, fake_musescore):
    res = render_audio(DORICO_LIKE, tmp_path)

    assert res.ok
    assert fake_musescore["musicxml"][0].find(f"part[@id='{COUNT_IN_ID}']") is None
    assert res.sounds.transposed == [] and res.sounds.count_in_bars == 0


def test_every_mp3_gets_the_master_volume_that_keeps_the_full_mix_below_full_scale(
    tmp_path, fake_musescore, monkeypatch
):
    from xsatz import audio

    sounds = [Sound("Orchestra", 0, 32), None, None]
    monkeypatch.setattr(audio, "part_sounds", lambda root, settings: sounds)
    settings = AudioSettings()
    fake_musescore["peak"] = 2.0

    res = render_audio(DORICO_LIKE, tmp_path, settings)

    # A peak of twice full scale needs 6 dB less, and 1 dB more of headroom.
    assert res.master_db == pytest.approx(-1 - 20 * math.log10(2.0))
    mixes = dict(fake_musescore["mp3"])
    assert {round(m["master"]["volumeDb"], 2) for m in mixes.values()} == {-7.02}
    full = mixes["dorico_like.mp3"]["tracks"]
    assert full[0]["in"]["resourceMeta"]["id"] == "Orchestra\\0\\32"


def test_a_quiet_full_mix_keeps_its_level(tmp_path, fake_musescore):
    fake_musescore["peak"] = 0.25

    assert render_audio(DORICO_LIKE, tmp_path).master_db == 0.0


def test_wav_peak_reads_pcm_and_float(tmp_path):
    pcm, ieee = tmp_path / "pcm.wav", tmp_path / "float.wav"
    pcm.write_bytes(_wav([0.1, -0.5, 0.25], 1))
    ieee.write_bytes(_wav([0.1, -1.5, 0.25], 3))

    assert wav_peak(pcm) == pytest.approx(0.5, abs=1e-4)
    assert wav_peak(ieee) == pytest.approx(1.5)


def test_practice_mp3s_keep_the_own_part_and_the_count_in(tmp_path, fake_musescore):
    settings = AudioSettings(
        sounds={"drum": Sound("Kit", 128, 8)}, count_in=CountIn(), reverb=0.4, softer=10
    )

    render_audio(DORICO_LIKE, tmp_path, settings)

    mixes = dict(fake_musescore["mp3"])
    full = mixes["dorico_like.mp3"]["tracks"]
    assert [t["out"]["volumeDb"] for t in full] == [0, 0, 0, 0]
    assert [t["out"]["auxSends"][0]["signalAmount"] for t in full] == [0.4] * 4
    # The fixture names no instrument sounds, so no part matches the drum sound.
    assert all("in" not in t for t in full)
    # The own part and the count-in stay, the others play 10 dB softer.
    drums = mixes["dorico_like - Drum Kit.mp3"]["tracks"]
    assert [t["out"]["volumeDb"] for t in drums] == [-10, 0, -10, 0]


def test_with_midi_the_practice_midis_are_written_as_well(tmp_path, fake_musescore):
    res = render_audio(DORICO_LIKE, tmp_path, AudioSettings(count_in=CountIn()), midi=True)

    assert res.full_midi == tmp_path / "dorico_like.mid"
    assert [p.midi.name for p in res.practice] == [
        "dorico_like - Trombone.mid",
        "dorico_like - Drum Kit.mid",
        "dorico_like - Timpani.mid",
    ]
    # The own part and the count-in keep their velocities, the others play 15 dB softer.
    velocities = _velocities(res.practice[1].midi.read_bytes())
    assert velocities == [[34, 42, 0], [80, 100, 0], [34, 42, 0], [80, 100, 0]]


def test_no_practice_midis_when_the_tracks_do_not_match(tmp_path, fake_musescore, monkeypatch):
    real = musescore.run

    def run(args, timeout=300):
        target = Path(args[args.index("-o") + 1])
        if target.suffix == ".mid":
            target.write_bytes(_midi(1))
            return subprocess.CompletedProcess(args, 0, "", "")
        return real(args, timeout)

    monkeypatch.setattr(musescore, "run", run)

    res = render_audio(DORICO_LIKE, tmp_path, midi=True)

    assert res.ok and res.full_midi is not None
    assert all(p.midi is None for p in res.practice) and all(p.mp3 for p in res.practice)
    assert "no practice MIDIs" in res.log


def test_render_audio_fails_without_import(tmp_path, monkeypatch):
    monkeypatch.setattr(
        musescore, "run", lambda args, timeout=300: subprocess.CompletedProcess(args, 1, "", "x")
    )

    res = render_audio(DORICO_LIKE, tmp_path)

    assert not res.ok
    assert not list(tmp_path.iterdir())


def test_a_shaped_soundfont_is_written_once_and_played_instead(
    tmp_path, fake_musescore, monkeypatch
):
    from test_soundfont import _swelling, sf2

    from xsatz import audio

    font = tmp_path / "fonts" / "Orchestra.sf2"
    font.parent.mkdir()
    font.write_bytes(sf2([(0, 27, -12000)], [_swelling(1000, 400)]))
    sounds = [Sound("Orchestra", 0, 27, 0.5, 0.01), None, Sound("Other", 0, 1)]
    monkeypatch.setattr(audio, "part_sounds", lambda root, settings: sounds)
    settings = AudioSettings(soundfont_dir=font.parent)

    res = render_audio(DORICO_LIKE, tmp_path / "out", settings)

    copy = font.with_name("Orchestra-swell50-fade10ms.sf2")
    assert res.shaped == [copy] and copy.exists()
    full = dict(fake_musescore["mp3"])["dorico_like.mp3"]["tracks"]
    assert full[0]["in"]["resourceMeta"]["id"] == "Orchestra-swell50-fade10ms\\0\\27"
    assert full[2]["in"]["resourceMeta"]["id"] == "Other\\0\\1"
    written = copy.stat().st_mtime_ns
    render_audio(DORICO_LIKE, tmp_path / "out", settings)
    assert copy.stat().st_mtime_ns == written


def test_shaping_needs_the_soundfont_dir_and_file(tmp_path, fake_musescore, monkeypatch):
    from xsatz import audio

    sounds = [Sound("Orchestra", 0, 27, 0.5), None, None]
    monkeypatch.setattr(audio, "part_sounds", lambda root, settings: sounds)

    with pytest.raises(ValueError, match="soundfont_dir"):
        render_audio(DORICO_LIKE, tmp_path, AudioSettings())
    with pytest.raises(ValueError, match="Orchestra.sf2"):
        render_audio(DORICO_LIKE, tmp_path, AudioSettings(soundfont_dir=tmp_path))
