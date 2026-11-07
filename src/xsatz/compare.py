"""Compare a reference PDF (Dorico) with a generated PDF page by page.

Each page yields side-XX.png (side by side) and overlay-XX.png (reference red, new blue,
match black). The overlap (IoU of the ink pixels) is only a rough trend indicator -
look at the images!"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw


@dataclass
class PageScore:
    page: int
    overlap: float
    ink_ref: float
    ink_new: float


@dataclass
class CompareResult:
    pages_ref: int
    pages_new: int
    size_ref: tuple[float, float]
    size_new: tuple[float, float]
    scores: list[PageScore] = field(default_factory=list)
    out_dir: Path | None = None

    @property
    def mean_overlap(self) -> float:
        return float(np.mean([s.overlap for s in self.scores])) if self.scores else 0.0


def _rasterize(pdf: Path, dpi: int) -> tuple[pymupdf.Document, list[Image.Image]]:
    doc = pymupdf.open(pdf)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return doc, images


def _ink(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L")) < 160


def compare(
    ref: str | Path, new: str | Path, out_dir: str | Path | None = None, dpi: int = 60
) -> CompareResult:
    """Compare ``ref`` with ``new`` and write the images to ``out_dir``.

    Without ``out_dir`` the images go to ``<new stem>-compare/`` next to ``new``.
    """
    ref, new = Path(ref), Path(new)
    out = Path(out_dir) if out_dir is not None else new.parent / f"{new.stem}-compare"
    out.mkdir(parents=True, exist_ok=True)
    rdoc, ref_pages = _rasterize(ref, dpi)
    ndoc, new_pages = _rasterize(new, dpi)
    result = CompareResult(
        len(ref_pages),
        len(new_pages),
        (rdoc[0].rect.width, rdoc[0].rect.height),
        (ndoc[0].rect.width, ndoc[0].rect.height),
        out_dir=out,
    )
    blank = Image.new("RGB", ref_pages[0].size, "white")
    for i in range(max(len(ref_pages), len(new_pages))):
        r = ref_pages[i] if i < len(ref_pages) else blank
        n = (new_pages[i] if i < len(new_pages) else blank).resize(r.size)

        side = Image.new("RGB", (r.width * 2 + 10, r.height), "gray")
        side.paste(r, (0, 0))
        side.paste(n, (r.width + 10, 0))
        draw = ImageDraw.Draw(side)
        draw.text((5, 5), "Dorico", fill="red")
        draw.text((r.width + 15, 5), "X-Satz", fill="blue")
        side.save(out / f"side-{i + 1:02d}.png")

        ri, ni = _ink(r), _ink(n)
        overlay = np.full((*ri.shape, 3), 255, np.uint8)
        overlay[ri & ~ni] = (220, 0, 0)
        overlay[ni & ~ri] = (0, 0, 220)
        overlay[ri & ni] = (0, 0, 0)
        Image.fromarray(overlay).save(out / f"overlay-{i + 1:02d}.png")

        union = (ri | ni).sum()
        result.scores.append(
            PageScore(
                i + 1,
                float((ri & ni).sum() / union) if union else 1.0,
                float(ri.mean()),
                float(ni.mean()),
            )
        )
    return result


def format_result(res: CompareResult) -> str:
    lines = [
        f"Pages: Dorico {res.pages_ref} | X-Satz {res.pages_new}",
        f"Size: Dorico {res.size_ref[0]:.0f}x{res.size_ref[1]:.0f} pt | "
        f"X-Satz {res.size_new[0]:.0f}x{res.size_new[1]:.0f} pt",
    ]
    lines += [
        f"Page {s.page:>2}: overlap {s.overlap:5.1%}  ink {s.ink_ref:.2%} / {s.ink_new:.2%}"
        for s in res.scores
    ]
    lines.append(f"Mean overlap: {res.mean_overlap:.1%}  ->  images in {res.out_dir}")
    return "\n".join(lines)
