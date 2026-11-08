# X-Satz

[![CI](https://github.com/adminde/X-Satz/actions/workflows/ci.yml/badge.svg)](https://github.com/adminde/X-Satz/actions/workflows/ci.yml)
[![Licence: GPL-3.0-or-later](https://img.shields.io/badge/licence-GPL--3.0--or--later-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)

**From a Dorico MusicXML export to a print-ready full score, automatically.**

X-Satz was born in the Guggenmusik X-Treme, a carnival brass band. Our
musical director writes the arrangements in Dorico. Everything after that, the full score for
the conductor, the parts for the players, practice MIDIs and the numbers that tell brass
players which valves or slide positions to use, used to be manual work. X-Satz takes the
MusicXML export and produces these files on its own, with free software only.

## What it does today

- **Engraves a full score** from MusicXML with [MuseScore 4](https://musescore.org) on the
  command line, in a score style that follows the Dorico original: page format, system and
  page breaks, sizes, brackets, rehearsal marks and tempi. All text is set in EB Garamond.
- **Engraves the parts:** one PDF per instrument, every part at the same readable staff
  size and the same distance between the systems. Only when a third page would hold just one
  or two systems does X-Satz move the systems a little closer, and it never shrinks the notes.
- **Keeps the playing aids:** valve combinations, slide positions and timpani sticking that
  Dorico writes as lyrics under the notes, with their extender lines.
- **Handles percussion kits** with several instruments, voices and noteheads per staff.
- **Designs the title block and running header** with your band's logo and accent colour,
  passed in as configuration, never stored in the repository.
- **Keeps the page printable:** nothing sits closer than 5 mm to the edge of the paper.
- **Inspects:** `xsatz info` shows what a MusicXML file carries.

The original MusicXML file is never changed.

## How it works

MuseScore does the engraving. X-Satz works in stages around it, because some things cannot be
expressed in a style alone:

```
MusicXML ──▶ prepare ──▶ MuseScore import ──▶ edit ──▶ MuseScore export ──▶ finish ──▶ PDF
            (copy of the       (.mscz with       (frames       (PDF, PNG,        (logo and
             MusicXML)         score style)      MuseScore     MIDI, ...)        header rule)
                                                 needs)
```

A problem is solved in the earliest stage that can solve it: the style first, then the
MusicXML, then MuseScore's own file, then the PDF. The reasons and findings behind every
stage are recorded in [ADR 0008](docs/adr/0008-musescore-4-and-the-stages-around-it.md).

## Requirements

- **Python 3.11** or newer
- **[MuseScore Studio 4](https://musescore.org/download)**. X-Satz finds it in the usual install
  locations. Otherwise set the environment variable `MSCORE` to the MuseScore executable.
- **The fonts in [`libs/font/`](libs/README.md)** installed on the system. X-Satz sets every text
  in EB Garamond, MuseScore brings the music font Bravura itself.

X-Satz is developed on Windows, and its CI runs on Linux and Windows.

## Installation

```
git clone https://github.com/adminde/X-Satz.git
cd X-Satz
python -m venv .venv
.venv\Scripts\activate                # Linux/macOS: source .venv/bin/activate
python -m pip install -e .
xsatz doctor                          # checks Python and MuseScore
```

## Quick start

```
xsatz render march.musicxml --logo band-logo.png --color "#D6001C"
```

This writes `march.pdf` next to `march.musicxml`. Use `--out DIR` to write somewhere else.

```
xsatz parts march.musicxml --logo band-logo.png --color "#D6001C"
```

This writes one PDF per instrument, such as `march - Trumpet 1.pdf`, next to `march.musicxml`.

## Usage

| Command | What it does |
|---|---|
| `xsatz doctor` | Checks the setup and the MuseScore version |
| `xsatz info SCORE.musicxml` | Shows page layout, fonts, credits, parts, breaks and playing aids of a MusicXML file |
| `xsatz render SCORE.musicxml` | Renders the full score as PDF |
| `xsatz parts SCORE.musicxml` | Renders one PDF per part, `SCORE - PART.pdf` |

Options of `render`:

| Option | Meaning |
|---|---|
| `--out DIR` | Output directory, default: next to the input |
| `--fmt FORMAT` | `pdf` (default), `png`, `mscz`, `mid`, `musicxml` and other formats MuseScore writes |
| `--logo FILE` | Logo for title block and running header, PNG or SVG |
| `--color #RRGGBB` | Accent colour of the header rule |
| `--style FILE.mss` | Another MuseScore style instead of the X-Satz score style |
| `--raw` | Renders the original exactly as MuseScore imports it, without stages and style, to see what X-Satz changes |

`parts` takes `--out`, `--logo` and `--color` as well. Every part is set on A4 portrait with
a staff space of 1.75 mm and 12 staff spaces between its systems. When a third page would
hold only one or two systems, X-Satz tries 10 and then 8 staff spaces. A part that still needs more
than two pages is kept, and X-Satz prints a warning. The reasons are recorded in
[ADR 0009](docs/adr/0009-layout-of-the-full-score-and-the-parts.md).

## Configuration

Values that belong to a band or a person are never part of X-Satz. Pass them on the command
line, set them in the environment, or put them into `x-satz.conf`, a TOML file in the folder
you run `xsatz` from (start from [`x-satz.example.conf`](x-satz.example.conf)). Command line
options win over the environment, and the environment wins over the file.

```toml
[theme]
logo = "brand/logo.svg"   # relative to the folder of x-satz.conf
color = "#D6001C"
```

| `x-satz.conf` | Variable | Option | Meaning |
|---|---|---|---|
| `[theme] logo` | `XSATZ_LOGO` | `--logo` | Logo stamped into title block and running header, PNG or SVG. In an SVG, convert text to paths. Without a logo the PDF has none. |
| `[theme] color` | `XSATZ_COLOR` | `--color` | Accent colour of the rules as `#RRGGBB`. Without it X-Satz takes the accent colour of the logo. |
| | `MSCORE` | | Path to the MuseScore executable, when it is not found automatically |

An unknown section or key in `x-satz.conf` stops X-Satz with an error, so a typo does not go
unnoticed.

Titles and credits come from the MusicXML of the piece itself.

## Contributing

Contributions are welcome. Please read [AGENTS.md](AGENTS.md) first: it holds the rules for
everyone working on X-Satz, people and coding agents alike. The most important ones:

- **Never commit copyrighted scores** or anything made from them. Tests use public domain or
  self-made files only, and a pre-commit hook refuses PDFs and score files.
- **Everything in the repository is English.**
- **Decisions are recorded** as [architecture decision records](docs/adr/README.md).

Set up the development environment and run the gate before every pull request:

```
python -m pip install -e ".[dev]"
pre-commit install                    # checks on every commit and push
python tools/gates/verify.py          # pre-commit, tests and a real MuseScore render
```

The CI on GitHub runs the same gate on Linux and Windows.

## Project layout

```
src/xsatz/       the Python package and its command line
src/xsatz/styles the MuseScore styles of score and parts
docs/adr/        architecture decision records
libs/            third-party fonts with their licences
tests/           tests with public domain and self-made fixtures
tools/gates/     the gate
```

## Licence

X-Satz is free software under the [GNU General Public License v3.0 or later](LICENSE).

The Academico font in [`libs/font/academico/`](libs/font/academico/COPYING) is © Steinberg Media
Technologies GmbH and licensed under the SIL Open Font License 1.1. EB Garamond in
[`libs/font/garamond/`](libs/font/garamond/OFL.txt) is © The EB Garamond Project Authors
and licensed under the same licence. Third-party assets keep their own licences, listed in
[libs/README.md](libs/README.md).

## Acknowledgements

X-Satz stands on the work of [MuseScore](https://musescore.org) for the engraving,
[Bravura](https://github.com/steinbergmedia/bravura) and Academico by Steinberg and
[EB Garamond](https://github.com/octaviopardo/EBGaramond12) for the fonts,
and [PyMuPDF](https://pymupdf.readthedocs.io) for reading and finishing PDFs.
