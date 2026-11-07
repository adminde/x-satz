import os
from pathlib import Path

from xsatz.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "entchen.musicxml"


def test_info_command(capsys):
    assert main(["info", str(FIXTURE)], env_file=None) == 0
    assert "Trombone" in capsys.readouterr().out


def test_env_file_is_read_before_the_command(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    env.write_text("XSATZ_COLOR=#711611\n", encoding="utf-8")
    monkeypatch.delenv("XSATZ_COLOR", raising=False)

    assert main(["info", str(FIXTURE)], env_file=env) == 0

    assert os.environ["XSATZ_COLOR"] == "#711611"
    monkeypatch.delenv("XSATZ_COLOR")


def test_parts_command_warns_about_parts_longer_than_two_pages(tmp_path, monkeypatch, capsys):
    from xsatz import musescore, parts

    def render_parts(source, out_dir=None):
        long = tmp_path / "piece - Drums.pdf"
        long.write_text("pdf")
        return parts.PartsResult(Path(source), [parts.Part("Drums", long, 3, 5.0)], "")

    monkeypatch.setattr(musescore, "version", lambda: "4.7")
    monkeypatch.setattr(parts, "render_parts", render_parts)
    monkeypatch.delenv("XSATZ_LOGO", raising=False)

    assert main(["parts", str(FIXTURE)], env_file=None) == 0

    out = capsys.readouterr().out
    assert "piece - Drums.pdf: 3 pages, system distance 5 sp" in out
    assert "WARNING: Drums needs more than 2 pages" in out
