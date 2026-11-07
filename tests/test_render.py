import subprocess
import zipfile
from pathlib import Path

import pytest

from xsatz import musescore
from xsatz.render import render

SCORE = (
    '<?xml version="1.0" encoding="UTF-8"?><museScore version="4.70"><Score>'
    '<Staff id="1"><Measure/></Staff></Score></museScore>'
)


@pytest.fixture
def fake_musescore(monkeypatch):
    """Replace the MuseScore call by one that writes the target file given with -o."""
    calls: list[list[str]] = []

    def run(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        target = Path(args[args.index("-o") + 1])
        if target.suffix == ".mscz":
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("score.mscx", SCORE)
        else:
            target.write_text("pdf")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(musescore, "run", run)
    return calls


def test_render_writes_next_to_source_by_default(tmp_path, fake_musescore):
    source = tmp_path / "scores" / "piece.musicxml"
    source.parent.mkdir()
    source.write_text("<score-partwise/>")

    res = render(source)

    assert res.ok
    assert res.outputs == [source.parent / "piece.pdf"]


def test_render_writes_to_given_directory(tmp_path, fake_musescore):
    source = tmp_path / "piece.musicxml"
    source.write_text("<score-partwise/>")

    res = render(source, tmp_path / "out" / "nested", style=tmp_path / "score.mss")

    assert res.outputs == [tmp_path / "out" / "nested" / "piece.pdf"]
    assert fake_musescore[0][:2] == ["-S", str(tmp_path / "score.mss")]


DORICO_LIKE = Path(__file__).parent / "fixtures" / "dorico_like.musicxml"


def test_render_reads_a_prepared_copy_and_keeps_the_original(tmp_path, fake_musescore):
    before = DORICO_LIKE.read_bytes()

    res = render(DORICO_LIKE, tmp_path)

    imports, exports = fake_musescore
    read = Path(imports[-1])
    assert read != DORICO_LIKE
    assert read.name == "dorico_like.musicxml"
    assert not read.exists()  # the temporary copy is gone after rendering
    assert res.prepared is not None and res.prepared.credits_removed == 7
    assert DORICO_LIKE.read_bytes() == before
    # MuseScore imports into its own file, which gets the copyright frame, then exports.
    assert Path(imports[imports.index("-o") + 1]).suffix == ".mscz"
    assert exports == ["-o", str(tmp_path / "dorico_like.pdf"), imports[imports.index("-o") + 1]]
    assert res.copyright_frame


def test_mscz_output_is_the_edited_file(tmp_path, fake_musescore):
    res = render(DORICO_LIKE, tmp_path, fmt="mscz")

    assert len(fake_musescore) == 1
    with zipfile.ZipFile(res.outputs[0]) as archive:
        assert "copyright" in archive.read("score.mscx").decode("utf-8")


def test_raw_render_reads_the_original(tmp_path, fake_musescore):
    res = render(DORICO_LIKE, tmp_path, prepared=False)

    assert fake_musescore[0][-1] == str(DORICO_LIKE)
    assert res.prepared is None


def test_render_never_overwrites_its_source(tmp_path, fake_musescore):
    source = tmp_path / "piece.musicxml"
    source.write_text("<score-partwise/>")

    with pytest.raises(ValueError):
        render(source, fmt="musicxml")
    assert source.read_text() == "<score-partwise/>"
    assert fake_musescore == []


def test_default_style_ships_with_the_package():
    from xsatz.render import default_style

    style = default_style()
    assert style.name == "score.mss"
    assert "<musicalSymbolFont>Bravura</musicalSymbolFont>" in style.read_text(encoding="utf-8")
