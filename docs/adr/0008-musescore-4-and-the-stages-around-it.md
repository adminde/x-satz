# 0008. MuseScore 4 engraves, X-Satz works in stages around it

Date: 2026-11-07

## Status

Accepted

## Context

Dorico engraves the originals, but it is commercial, does not run on a Debian server and is
never to be touched. Data flows one way only: Dorico → MusicXML → X-Satz.

MuseScore 4 (GPL) reads MusicXML, runs headless on the command line, ships the SMuFL font
Bravura that Dorico uses as well, and takes style files (`.mss`). LilyPond and Verovio are free
alternatives that were not evaluated: LilyPond needs a MusicXML converter of its own, Verovio
renders SVG for the web rather than print.

The raw import of the reference score into MuseScore 4.7 showed that a style alone cannot get
close to the original. These findings come from `xsatz compare`, the content check and tests
with the public domain fixture:

- Dorico writes title block, headers and footers as `<credit>` elements with absolute
  positions on every page. MuseScore turned them into frames, one of them carried a page
  break onto a page of its own, and every later page was shifted. As soon as a file holds a
  single credit, MuseScore builds the whole title block from credits and ignores the metadata.
- Dorico writes rehearsal mark, section text and tempo as one `<direction>`. For files whose
  `<software>` names Dorico, MuseScore merges them and drops the rehearsal mark. Only separate
  directions together with a neutral `<software>` entry keep all of them.
- Dorico keeps a placeholder in `movement-title` and a credit line in the composer field.
- The sizes of the default fonts in `<defaults>` override the text sizes, bold and italic of
  the style. Without the defaults at all, MuseScore falls back to its own typeface Edwin.
- Page size and margins come from the MusicXML, never from the style.
- A percussion kit without MIDI data becomes a chain of instrument changes with merged voices.
  With MIDI data every drum set entry has a single notehead. A single percussion instrument
  with a sound MuseScore does not know becomes a pitched staff. Dorico exports the key of the
  score to percussion staves without showing it, and no part groups, and adds " (C)" to the
  names of C instruments.
- MuseScore drops `<credit-image>`, its headers and footers hold text only, and it has no
  margins for the first page alone.

## Decision

We will engrave with MuseScore 4.x only, called through `xsatz.musescore` with the path from
`MSCORE` or the automatic search, and work around it in stages:

1. **Prepare** (`xsatz.prepare`): a copy of the MusicXML in a temporary directory, never the
   original. It reads title, label, credit lines and copyright from the page 1 credits or
   the metadata, removes the credits, rewrites the metadata, splits combined directions with
   the rehearsal mark first and bold, removes the sizes of the default fonts, gives a single
   percussion instrument channel 10, turns every instrument and notehead of a kit into a
   drum set entry of its own, hides keys on percussion staves, removes " (C)" from names,
   adds part groups like the reference when there are none, writes page size and margins of
   the style into the copy, and replaces the `<software>` entry.
2. **Import**: MuseScore reads the copy with the score style `src/xsatz/styles/score.mss` and
   writes its own file (`.mscz`).
3. **Edit** (`xsatz.mscz`): changes MusicXML cannot carry, so far the copyright line in a
   frame after the system of page 1, 5 mm above the bottom edge.
4. **Export**: MuseScore writes the requested format from the edited file.
5. **Finish** (`xsatz.theme`): the logo left of the title and in the running header, and a rule
   in the configured accent colour under the title block and under every running header,
   stamped into the PDF at positions taken from the texts MuseScore drew. An SVG logo stays
   vector. One that embeds raster images is stamped as a single image of moderate size,
   because PDF viewers decode oversized embedded images anew on every page and keep
   redrawing the logo.

A problem is solved in the earliest stage that can: the style first, then the MusicXML, then
MuseScore's file, then the PDF. Every step names its finding and has a test. Manual rework of
a generated file is never part of the pipeline. Where it would still be needed, it is
recorded as a finding in this record. `--raw` renders the original in one pass without stages and style, to
measure what they change.

## Consequences

Everything stays free software and runs the same on Windows, Linux and in a container. The
reference score comes out with its page count, complete content including rehearsal marks
and percussion noteheads, brackets as in the original and the X-Satz title block.

X-Satz depends on how MuseScore treats its input, and it writes MuseScore's own file format,
which is no public interface. Every MuseScore update is checked with the gate, `xsatz compare`
and the content check, and the MuseScore version is pinned wherever PDFs must be reproducible.
Rendering starts MuseScore twice. The `.mscz` carries no logo, only the PDF does. The drum keys
of the percussion entries only tell entries apart and are no General MIDI sounds, so practice
MIDIs in phase 3 need a mapping to real sounds. Comments of the original MusicXML are not
carried into the copy.

The CI has no MuseScore, so the stage `render` of the gate runs only where MuseScore is
installed and is reported as "not checked" elsewhere.
