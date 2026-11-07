"""Overview of a MusicXML file: layout defaults, credits, parts, breaks, lyrics and
fingerings. Shows what Dorico actually exports."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PartInfo:
    name: str
    measures: int
    counts: Counter[str] = field(default_factory=Counter)


@dataclass
class ScoreInfo:
    path: Path
    scaling: tuple[str, str] | None = None  # (millimeters, tenths)
    page: dict[str, str] = field(default_factory=dict)
    fonts: dict[str, dict[str, str]] = field(default_factory=dict)
    credits: list[str] = field(default_factory=list)
    parts: list[PartInfo] = field(default_factory=list)


def load(path: Path) -> ET.Element:
    """Load MusicXML, uncompressed (.musicxml/.xml) or compressed (.mxl)."""
    if path.suffix.lower() == ".mxl":
        with zipfile.ZipFile(path) as z:
            container = ET.fromstring(z.read("META-INF/container.xml"))
            rootfile = container.find(".//rootfile")
            if rootfile is None:
                raise ValueError(f"{path}: no rootfile in the container")
            return ET.fromstring(z.read(rootfile.get("full-path", "")))
    return ET.parse(path).getroot()


def _text(el: ET.Element | None, xpath: str) -> str | None:
    found = el.find(xpath) if el is not None else None
    return found.text if found is not None and found.text else None


def analyze(path: str | Path) -> ScoreInfo:
    path = Path(path)
    root = load(path)
    info = ScoreInfo(path=path)

    defaults = root.find("defaults")
    if defaults is not None:
        mm, tenths = _text(defaults, "scaling/millimeters"), _text(defaults, "scaling/tenths")
        if mm and tenths:
            info.scaling = (mm, tenths)
        layout = {
            "page width": "page-layout/page-width",
            "page height": "page-layout/page-height",
            "left margin": "page-layout/page-margins/left-margin",
            "right margin": "page-layout/page-margins/right-margin",
            "top margin": "page-layout/page-margins/top-margin",
            "bottom margin": "page-layout/page-margins/bottom-margin",
            "system distance": "system-layout/system-distance",
            "staff distance": "staff-layout/staff-distance",
        }
        info.page = {k: v for k, x in layout.items() if (v := _text(defaults, x))}
        for tag in ("music-font", "word-font", "lyric-font"):
            if (el := defaults.find(tag)) is not None:
                info.fonts[tag] = dict(el.attrib)

    for credit in root.findall("credit"):
        words = " ".join(w.text.strip() for w in credit.findall("credit-words") if w.text)
        if words:
            info.credits.append(f"p.{credit.get('page', '1')}: {words}")

    names = {
        sp.get("id"): _text(sp, "part-name") or sp.get("id", "?")
        for sp in root.findall("part-list/score-part")
    }
    for part in root.findall("part"):
        measures = part.findall("measure")
        counts: Counter[str] = Counter()
        for m in measures:
            if (pr := m.find("print")) is not None:
                counts["new page"] += pr.get("new-page") == "yes"
                counts["new system"] += pr.get("new-system") == "yes"
            counts["notes"] += len(m.findall("note"))
            counts["lyrics"] += len(m.findall("note/lyric"))
            counts["fingerings"] += len(m.findall("note/notations/technical/fingering"))
            counts["words"] += len(m.findall("direction/direction-type/words"))
            counts["transpose"] += len(m.findall("attributes/transpose"))
        info.parts.append(PartInfo(names.get(part.get("id"), "?"), len(measures), counts))
    return info


def format_info(info: ScoreInfo) -> str:
    lines = [f"== {info.path}"]
    if info.scaling:
        lines.append(f"Scaling: {info.scaling[0]} mm = {info.scaling[1]} tenths")
    else:
        lines.append("No scaling in <defaults> - layout probably not exported.")
    lines += [f"{k}: {v}" for k, v in info.page.items()]
    lines += [f"{k}: {v}" for k, v in info.fonts.items()]
    lines += [f"Credit {c[:80]}" for c in info.credits]
    lines.append(f"\n{len(info.parts)} parts")
    for p in info.parts:
        detail = "  ".join(f"{k}: {v}" for k, v in p.counts.items() if v)
        lines.append(f"- {p.name:<22} measures {p.measures:>4}  {detail}")
    return "\n".join(lines)
