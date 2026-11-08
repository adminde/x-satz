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
- Give new code tests (`pytest`). Look at the pages before and after every style or
  preprocessing change.
- Invent nothing: no measurements, figures or data that were not collected. What was not
  measured is called "not collected". Claim nothing you have not seen: a green gate is no
  acceptance.
- Propose an ADR when a decision matches the triggers in [docs/adr/README.md](docs/adr/README.md).
- Build only what the current task needs. Delete dead code.

### Ask first

- Committing, pushing, opening a pull request and merging it.
- Adding, removing or raising a dependency, an external program or a pinned version (Ruff,
  actions, pre-commit hooks).
- Adding an asset to `libs/`.
- Anything that contradicts an ADR. A changed decision gets a new record.

### Never

- Modify, move or overwrite the original scores, or commit them or anything derived from
  them: PDFs, images, excerpts, titles or credits of the pieces
  ([ADR 0003](docs/adr/0003-public-repository-without-protected-or-personal-data.md)).
- Put personal or organisational data (arrangers, credits, copyright lines, contact data,
  credentials), `x-satz.conf` or `.env` files into the repository
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

Personal and organisational data come from `x-satz.conf` or the environment at run time
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
  cli.py        # argparse subcommands: doctor, info, render, parts, audio
  musescore.py  # find MuseScore (env MSCORE) and run it headless
  xmlinfo.py    # MusicXML analysis (.musicxml/.xml/.mxl)
  config.py     # x-satz.conf for the command line, never read by the API (ADR 0003)
  prepare.py    # prepared copy of the MusicXML before MuseScore reads it (ADR 0008)
  render.py     # MusicXML -> pdf/png/mscz/mid through MuseScore, prepared and styled
  parts.py      # one PDF per part, extracted by MuseScore and fitted to 2 pages (ADR 0009)
  mscz.py       # edits of MuseScore's own files between import and export (ADR 0008-0010)
  theme.py      # logo and accent rules stamped into the finished PDF (ADR 0008)
  sounds.py     # sounding copy of the MusicXML and the sounds of the parts (ADR 0010)
  audio.py      # MP3 and MIDI of the band and one practice file per part (ADR 0010)
  soundfont.py  # shaped copies of SF2 SoundFonts: later sample starts, shorter fade-ins
  styles/       # score.mss and part.mss, the styles shipped with the package
tests/          # pytest, fixtures: entchen.musicxml (public domain), dorico_like.musicxml (self-made)
tools/gates/    # the gate, verify.py
docs/adr/       # architecture decision records
libs/           # third-party assets (fonts), unmodified, with licence, listed in libs/README.md
```

`libs/` is part of the repository but not of the Python package
([ADR 0004](docs/adr/0004-third-party-assets-in-libs.md)). MuseScore takes fonts from the
operating system, so the fonts in `libs/font/` have to be installed once per machine (see
`libs/README.md`). The reference scores use Academico for all text. X-Satz sets every
text of the full score and the parts in EB Garamond.

Later subcommands will produce MIDIs. Add new functionality as a module of its own plus a
subcommand.

## Local scores

The scores X-Satz is developed with, their Dorico reference PDFs, the band logo and every
result made from them exist only on development machines, outside of what git tracks. Where
they lie is a local matter and is not written down in the repository. The package never
reads them on its own, they are only passed in on the command line, and results go
elsewhere with `--out`:

```
xsatz render PIECE.musicxml --out OUT --logo LOGO.png
xsatz render PIECE.musicxml --out OUT/raw --raw     # as MuseScore imports it
xsatz parts PIECE.musicxml --out OUT/parts          # one PDF per part
xsatz audio PIECE.musicxml --out OUT/audio         # MP3 of the band and per part, --midi too
```

The scores are originals. The logo reaches X-Satz only through `--logo` or the environment
variable `XSATZ_LOGO`, its accent colour through `--color` or `XSATZ_COLOR`
([ADR 0003](docs/adr/0003-public-repository-without-protected-or-personal-data.md)). The file
names of the scores are those of the pieces. Do not copy them into the repository.

## Current phase: 2 – one readable part per instrument on at most 2 pages

Phase 1 is done: the full score PDF with the score style `src/xsatz/styles/score.mss` and the
stages of [ADR 0008](docs/adr/0008-musescore-4-and-the-stages-around-it.md).

Goal: `xsatz parts` turns the MusicXML into one PDF per instrument, each with a layout of its
own, readable and on at most 2 pages so that it fits side by side on a music stand.

Success criteria, in this order:
1. Every part carries all musical content of its instrument: notes, dynamics, articulation,
   playing aid numbers, rehearsal marks, tempi and section titles.
2. Readability first: the staff size is the same in every part and never shrinks to save
   pages. The systems keep the same distance in every part and shrink only from 12 to 10
   or 8 staff spaces when that saves a third page with one or two systems. A part that needs more
   pages even then is reported, not squeezed further.
3. The X-Satz design as in the full score: logo and accent colour from configuration, title
   and credits from the MusicXML, the part name in the title block and the running header,
   the copyright on page 1 only.

There is no Dorico reference for the parts, so they are judged by eye. The decisions and
findings are recorded in [ADR 0009](docs/adr/0009-layout-of-the-full-score-and-the-parts.md).

Deliverable: the parts of the reference piece, accepted by the maintainer, with the part
style `src/xsatz/styles/part.mss` and the stages of ADR 0009.

### What we know about the reference scores

Analysed from the Dorico reference PDFs and their MusicXML exports:
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

## Outlook (do not build now)

- Phase 3: MIDIs at concert pitch (transpositions/octaves), practice MIDIs per part.
- Phase 4: generate playing aids automatically (slide positions, valve combinations),
  configurable alternative positions, own tables, for example for a fourth valve.
- Later: integration, possibly Nextcloud – the director drops a MusicXML into a folder,
  results appear next to it. Not decided, see "Keep in mind" above.
