"""Stamp the band logo and the header rule into a finished PDF (ADR 0008).

MuseScore sets every text of the design. Only the logo and the rule come from here, placed
relative to the texts MuseScore drew, so that a change of the style moves them along.
"""

from __future__ import annotations

import io
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

LOGO_ENV = "XSATZ_LOGO"
COLOR_ENV = "XSATZ_COLOR"
# The running header ends with "page / pages", see the score style.
PAGE_COUNT = re.compile(r"^\d+ / \d+$")
HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{6})$")
# Common printers leave the outer 4 to 5 mm of the paper blank.
PRINT_SAFE = 5 / 25.4 * 72
# Long side in pixels of a logo stamped as raster image: about 1200 dpi for the logo on page 1.
RASTER_SIDE = 1600
# Room kept free above the next text under the title block, for the circle of a rehearsal mark.
RULE_CLEARANCE = 3.0
# Least room between the logo on page 1 and the title.
LOGO_GAP = 6.0

Color = tuple[float, float, float]


@dataclass
class StampResult:
    pdf: Path
    logo: Path
    pages: int
    rules: int
    color: Color
    warnings: list[str] = field(default_factory=list)


def logo_from_env() -> Path | None:
    """Path of the logo from the environment, or None when it is not configured."""
    value = os.environ.get(LOGO_ENV, "").strip()
    return Path(value) if value else None


def parse_color(value: str) -> Color:
    """An accent colour written as #RRGGBB, as RGB values from 0 to 1."""
    match = HEX_COLOR.match(value.strip())
    if match is None:
        raise ValueError(f"colour must be written as #RRGGBB: {value!r}")
    digits = match.group(1)
    red, green, blue = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return (red, green, blue)


def color_from_env() -> Color | None:
    """Accent colour from the environment, or None when it is not configured."""
    value = os.environ.get(COLOR_ENV, "").strip()
    return parse_color(value) if value else None


@dataclass
class _Logo:
    """A logo ready to stamp: a raster image or a vector page, cut to its visible part."""

    ratio: float
    accent: Color
    image: bytes | None = None
    vector: pymupdf.Document | None = None
    clip: pymupdf.Rect | None = None

    def stamp(self, page: pymupdf.Page, rect: pymupdf.Rect) -> None:
        if self.vector is not None:
            page.show_pdf_page(rect, self.vector, 0, clip=self.clip)
        else:
            page.insert_image(rect, stream=self.image)


def _load(logo: Path, warnings: list[str]) -> _Logo:
    if logo.suffix.lower() == ".svg":
        return _load_svg(logo, warnings)
    image = Image.open(logo).convert("RGBA")
    box = image.getchannel("A").getbbox() or (0, 0, image.width, image.height)
    image = image.crop(box)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return _Logo(image.width / image.height, _accent(image), image=buffer.getvalue())


def _render(page: pymupdf.Page, long_side: int) -> Image.Image:
    scale = long_side / max(page.rect.width, page.rect.height)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 4)
    return Image.fromarray(pixels, "RGBA")


def _load_svg(logo: Path, warnings: list[str]) -> _Logo:
    """An SVG logo as vector page, cut to the area its drawing covers.

    An SVG that embeds raster images is stamped as one image of RASTER_SIDE pixels instead.
    Its embedded images are often far larger than the printed logo, and PDF viewers decode
    them anew on every page, so the logo keeps redrawing while the page is shown.
    """
    source = logo.read_text(encoding="utf-8", errors="ignore")
    if "<text" in source:
        # MuPDF draws SVG text only in its built-in fonts, so a logo font would be replaced.
        warnings.append(
            f"{logo.name} contains text, which is drawn in a substitute font. "
            "Convert the text to paths in the drawing program."
        )
    vector = pymupdf.open("pdf", pymupdf.open(logo).convert_to_pdf())
    page = vector[0]
    preview = _render(page, 400)
    box = preview.getchannel("A").getbbox() or (0, 0, preview.width, preview.height)
    scale = 400 / max(page.rect.width, page.rect.height)
    clip = pymupdf.Rect(*(value / scale for value in box)) & page.rect
    accent = _accent(preview.crop(box))
    if "<image" not in source:
        return _Logo(clip.width / clip.height, accent, vector=vector, clip=clip)
    full = _render(page, RASTER_SIDE)
    full = full.crop(full.getchannel("A").getbbox() or (0, 0, full.width, full.height))
    buffer = io.BytesIO()
    full.save(buffer, format="PNG", optimize=True)
    return _Logo(full.width / full.height, accent, image=buffer.getvalue())


def _accent(image: Image.Image) -> tuple[float, float, float]:
    """Mean colour of the strongly saturated, opaque pixels, or black without any."""
    pixels = np.asarray(image, dtype=float)
    rgb, alpha = pixels[..., :3], pixels[..., 3]
    picked = rgb[(alpha > 200) & (rgb.max(axis=-1) - rgb.min(axis=-1) > 100)]
    if picked.size == 0:
        return (0.0, 0.0, 0.0)
    red, green, blue = (picked.mean(axis=0) / 255).tolist()
    return (red, green, blue)


def _spans(page: pymupdf.Page, flags: int | None = None) -> list[dict]:
    options = {} if flags is None else {"flags": flags}
    return [
        span
        for block in page.get_text("dict", **options)["blocks"]
        for line in block.get("lines", [])
        for span in line["spans"]
        if span["text"].strip()
    ]


def _title_block_rule(page: pymupdf.Page, block: set[str]) -> float | None:
    """Height of a rule between the title block and what follows it, or None without room.

    ``block`` holds the texts of the title block besides the title. The rule sits halfway
    between the lowest of them and the highest text below, which leaves room for the circle
    MuseScore draws around a rehearsal mark. Texts are measured by the outlines of their
    glyphs, because the boxes of music symbols and of italic texts reach far beyond them.
    """
    spans = _spans(page, pymupdf.TEXT_ACCURATE_BBOXES)
    title = max(spans, key=lambda s: s["size"])
    ours = [s for s in spans if s is title or s["text"].strip() in block]
    bottom = max(s["bbox"][3] for s in ours)
    texts = {s["text"].strip() for s in ours}
    below = [
        s["bbox"][1] for s in spans if s["text"].strip() not in texts and s["bbox"][1] > bottom
    ]
    if not below:
        return None
    next_top = min(below) - RULE_CLEARANCE
    if next_top - bottom < 2 * RULE_CLEARANCE:
        return None
    return (bottom + next_top) / 2


def stamp_logo(
    pdf: str | Path,
    logo: str | Path,
    color: Color | None = None,
    margin: float = 36.0,
    title_block: Sequence[str] = (),
) -> StampResult:
    """Stamp ``logo`` into ``pdf`` in place.

    The header rule takes ``color``, or without it the accent colour of the logo. ``margin``
    is the left and right page margin. With the texts of the title block besides the title,
    page 1 gets a rule under the title block as well.
    """
    pdf, logo = Path(pdf), Path(logo)
    if not logo.is_file():
        raise FileNotFoundError(f"logo not found: {logo}")
    warnings: list[str] = []
    loaded = _load(logo, warnings)
    ratio = loaded.ratio
    accent = color if color is not None else loaded.accent
    doc = pymupdf.open(pdf)
    rules = 0
    for number, page in enumerate(doc):
        spans = _spans(page)
        if number == 0:
            # The title is the largest text on the first page.
            title = max(spans, key=lambda s: s["size"], default=None)
            if title is None:
                continue
            top, bottom = title["bbox"][1], title["bbox"][3]
            height = (bottom - top) * 1.5
            # On a narrow page a long title leaves less room, and the logo shrinks to fit
            # left of it.
            room = title["bbox"][0] - margin - LOGO_GAP
            if height * ratio > room:
                height = room / ratio
            y = max(top - (height - (bottom - top)) / 2, PRINT_SAFE)
            if height > 0:
                loaded.stamp(page, pymupdf.Rect(margin, y, margin + height * ratio, y + height))
            block = {text.strip() for text in title_block if text.strip()}
            rule = _title_block_rule(page, block) if block else None
            if rule is not None:
                page.draw_line(
                    (margin, rule), (page.rect.width - margin, rule), color=accent, width=0.6
                )
                rules += 1
            continue
        header = next((s for s in spans if PAGE_COUNT.match(s["text"].strip())), None)
        if header is None:
            continue
        top, bottom = header["bbox"][1], header["bbox"][3]
        height = (bottom - top) * 1.3
        y = max(top - (height - (bottom - top)) / 2, PRINT_SAFE)
        loaded.stamp(page, pymupdf.Rect(margin, y, margin + height * ratio, y + height))
        rule = bottom + (bottom - top) * 0.5
        page.draw_line((margin, rule), (page.rect.width - margin, rule), color=accent, width=0.6)
        rules += 1
    pages = len(doc)
    stamped = pdf.with_name(pdf.name + ".stamped")
    doc.save(stamped, garbage=3, deflate=True)
    doc.close()
    stamped.replace(pdf)
    return StampResult(pdf, logo, pages, rules, accent, warnings)
