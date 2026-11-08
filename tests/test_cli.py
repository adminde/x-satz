from pathlib import Path

import pytest

from xsatz.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "entchen.musicxml"


def test_info_command(capsys):
    assert main(["info", str(FIXTURE)], settings_file=None) == 0
    assert "Trombone" in capsys.readouterr().out


def _parts_with_theme(monkeypatch, tmp_path, pages=2):
    """Run ``parts`` with stand-ins and return the logo, colour and mscz wish they get."""
    from xsatz import musescore, parts, theme

    stamped = {}

    def render_parts(source, out_dir=None, mscz=False):
        stamped["mscz"] = mscz
        pdf = tmp_path / "piece - Horn.pdf"
        pdf.write_text("pdf")
        return parts.PartsResult(Path(source), [parts.Part("Horn", pdf, pages, 12.0)], "")

    def stamp_logo(pdf, logo, color=None, **_):
        stamped.update(logo=logo, color=color)
        return theme.StampResult(Path(pdf), Path(logo), pages, pages, color or (0, 0, 0))

    monkeypatch.setattr(musescore, "version", lambda: "4.7")
    monkeypatch.setattr(parts, "render_parts", render_parts)
    monkeypatch.setattr(theme, "stamp_logo", stamp_logo)
    return stamped


def test_settings_file_gives_logo_and_colour(tmp_path, monkeypatch):
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[theme]\nlogo = "logo.svg"\ncolor = "#711611"\n', encoding="utf-8")
    stamped = _parts_with_theme(monkeypatch, tmp_path)

    assert main(["parts", str(FIXTURE)], settings_file=conf) == 0

    assert stamped["logo"] == tmp_path / "logo.svg"
    assert stamped["color"] == pytest.approx((0x71 / 255, 0x16 / 255, 0x11 / 255))


def test_options_win_over_the_settings_file(tmp_path, monkeypatch):
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[theme]\nlogo = "logo.svg"\ncolor = "#711611"\n', encoding="utf-8")
    stamped = _parts_with_theme(monkeypatch, tmp_path)
    options = ["--logo", str(tmp_path / "other.svg"), "--color", "#FFFFFF"]

    assert main(["parts", str(FIXTURE), *options], settings_file=conf) == 0

    assert stamped["logo"] == tmp_path / "other.svg"
    assert stamped["color"] == (1.0, 1.0, 1.0)


def test_broken_settings_file_stops_with_an_error(tmp_path, capsys):
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[brand]\nlogo = "logo.svg"\n', encoding="utf-8")

    assert main(["info", str(FIXTURE)], settings_file=conf) == 2
    assert "unknown section [brand]" in capsys.readouterr().out


def test_parts_command_warns_about_parts_longer_than_two_pages(tmp_path, monkeypatch, capsys):
    _parts_with_theme(monkeypatch, tmp_path, pages=3)

    assert main(["parts", str(FIXTURE)], settings_file=None) == 0

    out = capsys.readouterr().out
    assert "piece - Horn.pdf: 3 pages, system distance 12 sp" in out
    assert "WARNING: Horn needs more than 2 pages" in out


OUTPUT_MSCZ = "[output]\nmscz = true\n"


@pytest.mark.parametrize(
    ("conf", "option", "kept"),
    [
        ("", [], False),
        (OUTPUT_MSCZ, [], True),
        (OUTPUT_MSCZ, ["--no-mscz"], False),
        ("", ["--mscz"], True),
    ],
)
def test_mscz_option_wins_over_the_settings_file(tmp_path, monkeypatch, conf, option, kept):
    settings = tmp_path / "x-satz.conf"
    settings.write_text(conf, encoding="utf-8")
    stamped = _parts_with_theme(monkeypatch, tmp_path)

    assert main(["parts", str(FIXTURE), *option], settings_file=settings) == 0

    assert stamped["mscz"] is kept


@pytest.mark.parametrize(
    ("conf", "option", "midi"),
    [
        ("", [], False),
        ("[output]\nmidi = true\n", [], True),
        ("[output]\nmidi = true\n", ["--no-midi"], False),
        ("", ["--midi"], True),
    ],
)
def test_midi_option_wins_over_the_settings_file(tmp_path, monkeypatch, conf, option, midi):
    from xsatz import audio, musescore

    settings = tmp_path / "x-satz.conf"
    settings.write_text(conf, encoding="utf-8")
    asked = {}

    def render_audio(source, out_dir=None, sounds=None, midi=False):
        asked["midi"] = midi
        raise ValueError("stops here")

    monkeypatch.setattr(musescore, "version", lambda: "4.7")
    monkeypatch.setattr(audio, "render_audio", render_audio)

    assert main(["audio", str(FIXTURE), *option], settings_file=settings) == 2

    assert asked["midi"] is midi
