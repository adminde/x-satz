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
