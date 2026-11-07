from pathlib import Path

from xsatz.xmlinfo import analyze, format_info

FIXTURE = Path(__file__).parent / "fixtures" / "entchen.musicxml"


def test_analyze_fixture():
    info = analyze(FIXTURE)
    assert len(info.parts) == 1
    part = info.parts[0]
    assert part.measures == 10
    assert part.counts["notes"] == 27
    assert part.counts["lyrics"] == 27  # slide positions encoded as lyrics
    assert "1 parts" in format_info(info)
