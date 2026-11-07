"""Command line: xsatz <command> ..."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from xsatz import __version__, musescore
from xsatz.brand import parse_color
from xsatz.config import load_env_file


def _cmd_info(a: argparse.Namespace) -> int:
    from xsatz.xmlinfo import analyze, format_info

    for f in a.files:
        print(format_info(analyze(f)), end="\n\n")
    return 0


def _branding(a: argparse.Namespace) -> tuple[Path | None, tuple[float, float, float] | None]:
    """Logo and accent colour from the options, else from the environment."""
    from xsatz.brand import color_from_env, logo_from_env

    return a.logo or logo_from_env(), a.color or color_from_env()


def _cmd_render(a: argparse.Namespace) -> int:
    from xsatz.brand import stamp_logo
    from xsatz.render import default_style, render

    try:
        logo, color = _branding(a)
    except ValueError as exc:
        print(f"XSATZ_COLOR: {exc}")
        return 2
    print("MuseScore:", musescore.version())
    style = None if a.raw else (a.style or default_style())
    logo = None if a.raw else logo
    failed = 0
    for f in a.files:
        res = render(f, a.out, a.fmt, style, prepared=not a.raw)
        if res.prepared:
            p = res.prepared
            print(
                f"      prepared: {p.credits_removed} credits removed, "
                f"{p.directions_split} directions split, title {p.titles.title!r}"
            )
        if res.ok:
            print(f"OK    {res.source.name} -> {', '.join(map(str, res.outputs))}")
            if logo and a.fmt == "pdf":
                titles = res.prepared.titles if res.prepared else None
                block = [titles.label, *titles.lines] if titles else []
                stamp = stamp_logo(res.outputs[0], logo, color, title_block=block)
                print(f"      logo on {stamp.pages} pages, {stamp.rules} header rules")
                for warning in stamp.warnings:
                    print(f"      WARNING: {warning}")
        else:
            failed += 1
            print(f"FAIL  {res.source.name}\n{res.log}")
    return 1 if failed else 0


def _cmd_parts(a: argparse.Namespace) -> int:
    from xsatz.brand import stamp_logo
    from xsatz.parts import MAX_PAGES, render_parts

    try:
        logo, color = _branding(a)
    except ValueError as exc:
        print(f"XSATZ_COLOR: {exc}")
        return 2
    print("MuseScore:", musescore.version())
    failed = 0
    for f in a.files:
        res = render_parts(f, a.out)
        if not res.ok:
            failed += 1
            print(f"FAIL  {res.source.name}\n{res.log}")
            continue
        lines = res.prepared.titles.lines if res.prepared else []
        print(f"OK    {res.source.name}: {len(res.parts)} parts")
        for part in res.parts:
            print(
                f"      {part.output}: {part.pages} pages, "
                f"system distance {part.system_distance:g} sp"
            )
            if logo:
                stamp = stamp_logo(
                    part.output, logo, color, margin=res.margin, title_block=[part.name, *lines]
                )
                for warning in stamp.warnings:
                    print(f"      WARNING: {warning}")
            if part.breaks:
                print(f"      {part.breaks} system breaks before texts at the right margin")
            if part.pages > MAX_PAGES:
                print(f"      WARNING: {part.name} needs more than {MAX_PAGES} pages")
            for text in part.beyond_margin:
                print(f"      WARNING: {text!r} runs past the right margin")
    return 1 if failed else 0


def _cmd_compare(a: argparse.Namespace) -> int:
    from xsatz.compare import compare, format_result

    print(format_result(compare(a.ref, a.new, a.out, a.dpi)))
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    print(f"xsatz {__version__}, Python {sys.version.split()[0]}")
    try:
        exe = musescore.executable()
        ver = musescore.version()
        print(f"MuseScore: {ver}  ({exe})")
        if "4." not in ver:
            print("WARNING: MuseScore 4 is required.")
            return 1
    except musescore.MuseScoreNotFound as e:
        print(e)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xsatz", description="Dorico MusicXML -> scores and sound")
    p.add_argument("--version", action="version", version=f"xsatz {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="check the setup (MuseScore version etc.)")
    s.set_defaults(func=_cmd_doctor)

    s = sub.add_parser("info", help="analyse MusicXML files")
    s.add_argument("files", nargs="+", type=Path)
    s.set_defaults(func=_cmd_info)

    s = sub.add_parser("render", help="render MusicXML files with MuseScore")
    s.add_argument("files", nargs="+", type=Path)
    s.add_argument(
        "--style", type=Path, help="MuseScore style file (.mss), default: the X-Satz score style"
    )
    s.add_argument(
        "--raw",
        action="store_true",
        help="render the original as MuseScore imports it, without preparing and without style",
    )
    s.add_argument(
        "--logo", type=Path, help="logo for title block and header (default: env XSATZ_LOGO)"
    )
    s.add_argument(
        "--color",
        type=parse_color,
        help="accent colour of the header rule as #RRGGBB "
        "(default: env XSATZ_COLOR, else taken from the logo)",
    )
    s.add_argument("--out", type=Path, help="output directory (default: next to each input)")
    s.add_argument("--fmt", default="pdf", help="pdf, png, mscz, mid, musicxml ...")
    s.set_defaults(func=_cmd_render)

    s = sub.add_parser("parts", help="render one PDF per part of MusicXML files")
    s.add_argument("files", nargs="+", type=Path)
    s.add_argument(
        "--logo", type=Path, help="logo for title block and header (default: env XSATZ_LOGO)"
    )
    s.add_argument(
        "--color",
        type=parse_color,
        help="accent colour of the header rule as #RRGGBB "
        "(default: env XSATZ_COLOR, else taken from the logo)",
    )
    s.add_argument("--out", type=Path, help="output directory (default: next to each input)")
    s.set_defaults(func=_cmd_parts)

    s = sub.add_parser("compare", help="compare a reference PDF with a generated PDF")
    s.add_argument("ref", type=Path)
    s.add_argument("new", type=Path)
    s.add_argument(
        "--out", type=Path, help="image directory (default: <new stem>-compare next to new)"
    )
    s.add_argument("--dpi", type=int, default=60)
    s.set_defaults(func=_cmd_compare)
    return p


def main(argv: list[str] | None = None, env_file: Path | None = Path(".env")) -> int:
    """Run the command line. ``env_file`` is read first, the environment wins over it."""
    if env_file is not None:
        load_env_file(env_file, os.environ)
    args = build_parser().parse_args(argv)
    return args.func(args)
