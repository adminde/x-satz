# X-Satz

Score engraving tool of the Guggenmusik X-Treme (everything of ours is called X-…, that is
tradition). The musical director writes scores in Dorico and exports MusicXML. X-Satz turns
that into full-score PDFs automatically, later also parts, practice MIDIs and playing aids.
Data flows one way only: Dorico → MusicXML → X-Satz. Dorico is never touched.

This file is the shared guide for all coding agents. `CLAUDE.md` only imports it, so changes
belong here. The repository is public. Default branch: `main`.

| Read                                      | When                                              |
| ----------------------------------------- | ------------------------------------------------- |
| [README.md](README.md)                    | Setup and usage from the point of view of a user  |
| [docs/adr/](docs/adr/README.md)           | Why things are the way they are                   |
| [libs/README.md](libs/README.md)          | Which third-party assets exist, how to install them |

## Commands

```
python -m venv .venv              # once per clone
.venv\Scripts\activate            # Windows; Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]" # package in editable mode plus development tools
pre-commit install                # once per clone: hooks for commit and push
xsatz doctor                      # is MuseScore 4 found? (otherwise set MSCORE)
python tools/gates/verify.py      # the gate: pre-commit, pytest, render. 0 green, 1 red, 2 environment error
python -m pytest                  # tests alone
```

All commands run inside the activated virtual environment. The commit hook runs the file
checks and Ruff, the push hook runs the whole gate, and the CI (`.github/workflows/ci.yml`)
runs the same gate on Linux and Windows ([ADR 0007](docs/adr/0007-a-change-is-done-when-the-gate-is-green.md)).
The CI has no MuseScore, so the stage `render` is "not checked" there.

Dependencies are declared in `pyproject.toml`: runtime ones under `dependencies`, development
tools under the `dev` extra. Ruff is pinned there to the same version as the `ruff-pre-commit`
rev in `.pre-commit-config.yaml`; change both together.

### Always

- Write everything in English: code, comments, tests, output, docs, commits, branches
  ([ADR 0002](docs/adr/0002-english-as-the-only-repository-language.md)).
- Present a short plan first and wait for the OK. Ask when a source contradicts the task
  instead of deviating silently.
- Run `python tools/gates/verify.py` before every push. A change is done only when the gate
  is green. Say which stages ran, which were red and which were not checked.
- Work on `feature/<name>`, `fix/<name>` or `chore/<name>` and bring it into `main` only
  through a pull request, merged as a merge commit while the gate of its newest commit is
  green ([ADR 0007](docs/adr/0007-a-change-is-done-when-the-gate-is-green.md)).
- Read `git status` before every `git add` and stage your own files one by one, never with
  `git add -A` or `git add .`.
- Write commit messages as one English sentence in the imperative, subject at most 72
  characters, for example `Match the page margins of Dorico`. One commit per coherent change.
- Give new code tests (`pytest`). Back every style or preprocessing change with
  `xsatz compare` before and after, and look at the comparison images.
- Invent nothing: no measurements, figures or data that were not collected. What was not
  measured is called "not collected". Claim nothing you have not seen: a green gate is no
  acceptance, and a compare figure is no substitute for looking at the pages.
- Propose an ADR when a decision matches the triggers in [docs/adr/README.md](docs/adr/README.md).
- Build only what the current task needs. Delete dead code.

### Ask first

- Committing, pushing, opening a pull request and merging it.
- Adding, removing or raising a dependency, an external program or a pinned version (Ruff,
  actions, pre-commit hooks).
- Adding an asset to `libs/`.
- Anything that contradicts an ADR. A changed decision gets a new record.

### Never

- Modify, move or overwrite the originals in `data/`, or commit anything from `data/` or
  derived from the scores: PDFs, images, excerpts, titles or credits of the pieces
  ([ADR 0003](docs/adr/0003-public-repository-without-protected-or-personal-data.md)).
- Put personal or organisational data (arrangers, credits, copyright lines, contact data,
  credentials) or `.env` files into the repository
  ([ADR 0003](docs/adr/0003-public-repository-without-protected-or-personal-data.md)).
- Modify, rename, subset or convert files under `libs/<kind>/<name>/`
  ([ADR 0004](docs/adr/0004-third-party-assets-in-libs.md)).
- Give the package paths relative to the repository or the working directory, interactive
  input or global state ([ADR 0005](docs/adr/0005-package-independent-of-locations.md)).
- Commit working documents: drafts, plans, step lists, status notes, session notes. Only
  documentation of how X-Satz is built and used and ADRs belong here. Findings of
  experiments go into the context of the ADR whose decision they support.
- Skip hooks with `--no-verify` or `-n`.
- Add dependencies that are not free software (Debian server, club use without licence
  costs).
- Build ahead of a future need: no speculative abstractions, unused parameters or settings
  nobody sets.

### Comments

A comment explains why the code looks the way it does: the decision, the constraint or the
non obvious context. It must make sense without the session, chat or review that produced
it. No work in progress notes, no addressing the user or a reviewer, no change history, no
TODO or FIXME. Comments and docs are full sentences. If a comment has no real value, delete it.

```python
# Bad: narrates the change and restates the code.
# Fixed: now also looks for numbered files.
outputs = sorted(out_dir.glob(f"{source.stem}-*.{fmt}"))

# Good: explains why the code looks unusual.
# MuseScore writes one PNG per page as name-1.png, name-2.png, so the target name itself
# does not exist after a PNG export.
outputs = sorted(out_dir.glob(f"{source.stem}-*.{fmt}"))
```

## Architecture

The core is the Python package `xsatz` (src layout, `pyproject.toml`, CLI `xsatz`).
It is file based only: MusicXML in, files out. Every function returns data (dataclasses);
printing and formatting happen only in `cli.py`.

The package does not depend on any location ([ADR 0005](docs/adr/0005-package-independent-of-locations.md)):
input files and directories are always passed in, output directories are optional and default
to the directory of the input. Resources that ship with X-Satz, such as MuseScore styles, live
inside the package (`src/xsatz/styles/`) and are loaded with `importlib.resources`.

Personal and organisational data come from configuration or `.env` at run time
([ADR 0003](docs/adr/0003-public-repository-without-protected-or-personal-data.md)).

Engraving is done by MuseScore 4 on the command line
([ADR 0008](docs/adr/0008-musescore-4-and-the-stages-around-it.md)).

**Keep in mind, not decided:** a later step may run X-Satz inside Nextcloud (for example as an
ExApp through AppAPI with `nc_py_api` in a Docker container, with MuseScore inside). Nothing is
decided about it, so do not build anything for it and do not record it as an ADR. Just keep the
core usable as a library by another application: return data instead of printing, accept any
path, no interactive input, no global state.

### Repository layout

```
src/xsatz/
  cli.py        # argparse subcommands: doctor, info, render, compare
  musescore.py  # find MuseScore (env MSCORE) and run it headless
  xmlinfo.py    # MusicXML analysis (.musicxml/.xml/.mxl)
  config.py     # .env file for the command line, never read by the API (ADR 0003)
  prepare.py    # prepared copy of the MusicXML before MuseScore reads it (ADR 0008)
  render.py     # MusicXML -> pdf/png/mscz/mid through MuseScore, prepared and styled
  mscz.py       # edits of MuseScore's own file between import and export (ADR 0008)
  brand.py      # logo and header rule stamped into the finished PDF (ADR 0008)
  compare.py    # reference PDF vs. generated PDF, images and metrics
  styles/       # score.mss, the full score style shipped with the package
tests/          # pytest, fixture: tests/fixtures/entchen.musicxml (public domain)
tools/gates/    # the gate, verify.py
docs/adr/       # architecture decision records
libs/           # third-party assets (fonts), unmodified, with licence, listed in libs/README.md
```

`libs/` is part of the repository but not of the Python package
([ADR 0004](docs/adr/0004-third-party-assets-in-libs.md)). MuseScore takes fonts from the
operating system, so the fonts in `libs/font/` have to be installed once per machine (see
`libs/README.md`). The reference scores use Academico for all text.

Later subcommands will produce parts and PDFs, and MIDIs. Add new functionality as a module of
its own plus a subcommand.

## Local development data

`data/` is git-ignored and exists only on development machines. It is never read by the
package itself, only passed in on the command line:

```
data/XML/      # MusicXML exported from Dorico
data/PDF/      # PDFs exported from Dorico, the reference for comparisons
data/Dorico/   # Dorico projects
```

These files are originals. Write results to `data/out/` by passing `--out`, for example:

```
xsatz render data/XML/PIECE.musicxml --out data/out --logo data/Brand/LOGO.png
xsatz render data/XML/PIECE.musicxml --out data/out/raw --raw     # as MuseScore imports it
xsatz compare data/PDF/PIECE.pdf data/out/PIECE.pdf --out data/out/compare
```

The band logo lives in `data/Brand/` and reaches X-Satz only through `--logo` or the
environment variable `XSATZ_LOGO`, its accent colour through `--color` or `XSATZ_COLOR` ([ADR 0003](docs/adr/0003-public-repository-without-protected-or-personal-data.md)).

The file names in `data/` are those of the pieces. Do not copy them into the repository.

## Current phase: 1 – full-score PDF as close as possible to the Dorico original

Goal: generate a PDF from the MusicXML that looks as much as possible like the Dorico export.
This is about *insight*: what does MusicXML carry reliably, what gets lost, how far does
MuseScore 4 get with style adjustments?

Success criteria, in this order:
1. No musical content is missing (notes, dynamics, articulation, playing aid numbers, text).
2. Same page format, same page count, same bars per system and systems per page.
3. Same fonts and staff size, similar spacing.
4. Rehearsal marks as in the original. Title block, headers and footers follow the X-Satz
   design instead of Dorico: the band logo from configuration, title and credits from the
   MusicXML, a running header with logo, title and page number. Comparisons with the
   reference judge the music area; the title block and headers are judged by eye.

Deliverable: the full score PDF of the reference piece, accepted by the maintainer as
version 0.1, with the score style `src/xsatz/styles/score.mss` and the stages of
[ADR 0008](docs/adr/0008-musescore-4-and-the-stages-around-it.md).

### What we know about the reference

Analysed from the reference PDFs in `data/PDF/` and their MusicXML exports:
- **Dorico 5.1**, MusicXML 4.0, **A4 landscape** (841 × 594 pt), 13 and 14 pages.
- Scaling 4.339 mm = 40 tenths (staff space 1.085 mm), page margins 117 tenths left and right,
  146 tenths top and bottom. Every page carries a `<system-layout>` with left system margin
  and top system distance. Staff and system distances inside a system are not exported.
- Page breaks are explicit (`new-page="yes"`), every other measure says
  `new-system="no" new-page="no"`. Every page holds exactly one system of about 8 bars.
- Fonts: **Bravura**/BravuraText (music, SMuFL), **Academico** Regular/Bold/Italic (text),
  SourceSansPro (small text). MuseScore 4 ships Bravura. Academico is vendored in `libs/`.
- Instrumentation: trumpet 1–3, trombone 1–2, euphonium, sousaphone, hi-hat, toms, timpani,
  in one piece also body percussion. Brass in treble clef, trombones, euphonium and
  sousaphone with `octave-change -1`. Three flats and C major.
- **Playing aids are lyrics**, verse 1, below, `syllabic="single"`, held notes with
  `<extend>` and empty continuation entries: valve combinations for trumpet, euphonium and
  sousaphone ("0", "1", "23", "123" …), slide positions 1–7 and "2+" for the trombones,
  sticking "R"/"L" for the timpani. No `<fingering>`.
- Rehearsal marks are `<rehearsal enclosure="circle">` with the bar number, tempi
  `<metronome>` with `<sound tempo>`, section titles `<words>` in Academico 10, all in the top
  part only.
- Title block, headers and footers are `<credit>` elements with absolute positions on every
  page. Page 1: centred title, credits on the left and on the right, footer with a copyright
  line. Following pages: title as header, page number on the left on even and on the right on
  odd pages. Abbreviated instrument names come from `part-abbreviation` (Trp. 1 (C), Pos. 1,
  Euph. (C), Sousi, Hat, Tom, Pk).

### Suggested approach for phase 1

1. `xsatz doctor`: MuseScore **4** must be found.
2. Analyse every MusicXML with `xsatz info`.
3. Raw run without a style: `xsatz render` → `xsatz compare` → list the differences (look at
   the comparison images, do not trust the number alone).
4. Adjust `src/xsatz/styles/score.mss` iteratively (page format, margins, spatium, fonts,
   spacing, instrument names). Starting point: open the raw import in MuseScore 4, Format →
   Style, "Save style", then continue in a text editor.
5. Find out how MuseScore takes over layout from the MusicXML import (preferences → import →
   "import layout", "import system and page breaks") and how that applies on the command line.
6. Solve what styles cannot do as MusicXML preprocessing in the core (new module).

## Outlook (do not build now)

- Phase 2: individual parts with their own layout, goal "at most 2 pages, but readable"
  (shrink the staff size step by step down to a minimum).
- Phase 3: MIDIs at concert pitch (transpositions/octaves), practice MIDIs per part.
- Phase 4: generate playing aids automatically (slide positions, valve combinations),
  configurable alternative positions, own tables, for example for a fourth valve.
- Later: integration, possibly Nextcloud – the director drops a MusicXML into a folder,
  results appear next to it. Not decided, see "Keep in mind" above.
