from pathlib import Path

import pytest

from xsatz.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "entchen.musicxml"


def test_info_command(capsys):
    assert main(["info", str(FIXTURE)], settings_file=None) == 0
    assert "Trombone" in capsys.readouterr().out


def _parts_with_theme(monkeypatch, tmp_path, pages=2):
    """Run ``parts`` with stand-ins and return the logo and colour it stamps with."""
    from xsatz import musescore, parts, theme

    stamped = {}

    def render_parts(source, out_dir=None):
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
    monkeypatch.delenv("XSATZ_LOGO", raising=False)
    monkeypatch.delenv("XSATZ_COLOR", raising=False)
    stamped = _parts_with_theme(monkeypatch, tmp_path)

    assert main(["parts", str(FIXTURE)], settings_file=conf) == 0

    assert stamped["logo"] == tmp_path / "logo.svg"
    assert stamped["color"] == pytest.approx((0x71 / 255, 0x16 / 255, 0x11 / 255))


def test_options_and_environment_win_over_the_settings_file(tmp_path, monkeypatch):
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[theme]\nlogo = "logo.svg"\ncolor = "#711611"\n', encoding="utf-8")
    monkeypatch.setenv("XSATZ_LOGO", str(tmp_path / "env.svg"))
    monkeypatch.setenv("XSATZ_COLOR", "#000000")
    stamped = _parts_with_theme(monkeypatch, tmp_path)

    assert main(["parts", str(FIXTURE), "--color", "#FFFFFF"], settings_file=conf) == 0

    assert stamped["logo"] == tmp_path / "env.svg"
    assert stamped["color"] == (1.0, 1.0, 1.0)


def test_broken_settings_file_stops_with_an_error(tmp_path, capsys):
    conf = tmp_path / "x-satz.conf"
    conf.write_text('[brand]\nlogo = "logo.svg"\n', encoding="utf-8")

    assert main(["info", str(FIXTURE)], settings_file=conf) == 2
    assert "unknown section [brand]" in capsys.readouterr().out


def test_parts_command_warns_about_parts_longer_than_two_pages(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("XSATZ_LOGO", raising=False)
    _parts_with_theme(monkeypatch, tmp_path, pages=3)

    assert main(["parts", str(FIXTURE)], settings_file=None) == 0

    out = capsys.readouterr().out
    assert "piece - Horn.pdf: 3 pages, system distance 12 sp" in out
    assert "WARNING: Horn needs more than 2 pages" in out
