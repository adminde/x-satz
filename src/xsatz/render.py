"""MusicXML -> PDF/PNG/MSCZ/MID through MuseScore (headless)."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from xsatz import musescore
from xsatz.mscz import add_copyright_frame, shrink_blank_lines
from xsatz.prepare import PrepareResult, prepare


@dataclass
class RenderResult:
    source: Path
    outputs: list[Path]
    log: str
    prepared: PrepareResult | None = None
    copyright_frame: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.outputs)


def default_style() -> Path:
    """The full score style that ships with X-Satz."""
    return Path(str(resources.files("xsatz") / "styles" / "score.mss"))


def render(
    source: str | Path,
    out_dir: str | Path | None = None,
    fmt: str = "pdf",
    style: str | Path | None = None,
    prepared: bool = True,
) -> RenderResult:
    """Render ``source`` with MuseScore.

    Without ``out_dir`` the result is written next to ``source``. With ``prepared`` MuseScore
    reads a prepared copy of the MusicXML (ADR 0008) and the copyright goes into a frame on
    the first page of MuseScore's file before the export (ADR 0008). Otherwise MuseScore
    reads the original once.
    """
    source = Path(source)
    out_dir = Path(out_dir) if out_dir is not None else source.parent
    target = out_dir / f"{source.stem}.{fmt}"
    if target.resolve() == source.resolve():
        raise ValueError(f"{source}: rendering to {fmt} would overwrite the source")
    out_dir.mkdir(parents=True, exist_ok=True)
    styled = ["-S", str(style)] if style else []
    log = ""
    info = None
    frame = False
    with tempfile.TemporaryDirectory(prefix="xsatz-") as work:
        if not prepared:
            log += _run([*styled, "-o", str(target), str(source)])
        else:
            reads = Path(work) / f"{source.stem}.musicxml"
            info = prepare(source, reads, style)
            score = Path(work) / f"{source.stem}.mscz"
            log += _run([*styled, "-o", str(score), str(reads)])
            if score.exists():
                frame = add_copyright_frame(score, info.titles.rights)
                shrink_blank_lines(score)
                if fmt == "mscz":
                    shutil.copyfile(score, target)
                else:
                    log += _run(["-o", str(target), str(score)])
    # MuseScore writes one PNG per page as name-1.png, name-2.png, so the target name itself
    # does not exist after a PNG export.
    outputs = [target] if target.exists() else sorted(out_dir.glob(f"{source.stem}-*.{fmt}"))
    return RenderResult(source, outputs, log[-2000:], info, frame)


def _run(args: list[str]) -> str:
    res = musescore.run(args)
    return res.stdout + res.stderr
