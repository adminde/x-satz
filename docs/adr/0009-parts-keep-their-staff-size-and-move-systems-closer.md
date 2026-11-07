# 0009. Parts keep their staff size and move their systems closer

Date: 2026-11-07

## Status

Proposed

## Context

Phase 2 produces one PDF per instrument. A player should get at most two pages, which fit
side by side on a music stand, but the part must stay readable. The maintainer decided that
the staff size of a part never shrinks to reach two pages. Only the distance between the
systems may shrink, and only in an emergency: the systems keep 12 staff spaces, and move to
10 and then to 8 only when that saves a third page that would hold just one or two systems.
Parts with a different distance each, chosen as the largest that fits, looked uneven next
to each other.

MuseScore 4 makes parts on the command line, tested with MuseScore 4.7.6 and the reference
score:

- `--score-parts SCORE.mscz` prints a JSON document with the names of the parts and one
  MuseScore file per part, encoded in base64. `-P` exports nothing for a score imported from
  MusicXML, because such a score holds no parts yet.
- The parts take the style of the score with the part defaults of MuseScore: A4 portrait,
  a staff space of 1.75 mm, margins of 15 mm and multi-measure rests. The full score has a
  staff space of 1.085 mm on A4 landscape.
- The page and system breaks of the score do not reach the parts, so every part is laid out
  anew. Rehearsal marks, tempi, section titles and the playing aids appear in every part.
- Every part file carries a style of its own inside the score entry. It wins over the
  `score_style.mss` of the file, so replacing that file alone changes nothing.
- The title frame is copied with the label of the full score, plus a small part name above
  the title. At portrait width a long title runs into the credit lines.
- The copyright frame of the full score ([ADR 0008](0008-musescore-4-and-the-stages-around-it.md))
  is copied too. Without its page break it lands after the second system of page 1.
- The rule under the title block of page 1 needs a gap between the title block and the
  first text of the music. The box of an italic part name reaches below its letters, so
  measured by boxes that gap vanished in five parts once the tempo marks moved up beside
  the rehearsal marks, and the rule was left out.
- MuseScore sets a section title from the start of its measure. When that measure ends a
  narrow system, for example a multi-measure rest, the title runs past the right margin and
  off the paper. The PDF then holds only the part of the text that is on the paper.
- The texts of the playing aids, the bar numbers and the rehearsal marks have fixed sizes in
  points. At the larger staff of a part they looked too small.
- MuseScore stacks the section title and the tempo mark above the rehearsal mark of their
  measure. In a part each such stack pushed its system far away from the one above.
- The score style sets tempo marks 5 staff spaces above the staff, above the rehearsal marks.
  In a part a tempo mark without a rehearsal mark then pushed its whole system away from the
  one above.
- Academico, the text font of the Dorico originals and of the full score so far, has no
  weight below Regular. In a part its texts looked heavy next to the airier Dorico score. Of the fonts tried, MuseScore did not
  find the weights of variable fonts and set the texts in Tahoma instead, Source Serif 4 and
  Crimson Pro looked too modern, and the old style figures of Cormorant Garamond make a "1"
  look like an "I", which a playing aid cannot afford. EB Garamond, a classical serif that
  is lighter than Academico, has lining figures and a bold weight for the rehearsal marks.
- MuseScore spreads the systems of a page that is not full. Page 1 of a part is full because
  of the title block, page 2 is not, so the systems stood visibly further apart on page 2.
- With the part defaults, 4 of the 10 parts of the reference score had three pages. Without
  the copyright frame 2 had three, with a minimal system distance of 5 staff spaces 1. The
  hi-hat part has about 27 systems, 10 to 12 fit on a page even at 4 staff spaces, so no
  distance brings it down to two pages at this staff size.

Options that were weighed: one MusicXML per part through the full score pipeline would need
X-Satz to copy rehearsal marks, tempi and section titles into every part, which Dorico
writes into the top part only. Shrinking the staff size step by step was the first plan and
was rejected by the maintainer in favour of readability.

## Decision

We will render parts with `xsatz parts`, implemented in `xsatz.parts`, in these stages:

1. **Prepare and import** the MusicXML with the score style, as for the full score
   ([ADR 0008](0008-musescore-4-and-the-stages-around-it.md)), without the copyright frame.
2. **Extract**: `--score-parts` gives one MuseScore file per part.
3. **Edit** every part (`xsatz.mscz.edit_part`): remove its own style and the font families
   the import wrote into single texts, put the part style `src/xsatz/styles/part.mss` in
   place, write the part name as label of the title block, remove MuseScore's small part
   name and make the title frame tall enough for the title above the credit lines.
4. **Export** all parts with one MuseScore job into the working directory.
5. **Arrange**: after the first export, the section titles at every rehearsal mark move
   beside the mark, measured in the PDF (`xsatz.parts`, `xsatz.mscz.place_beside_mark`).
   They follow the mark flush left, or stand before it flush right where they would run
   past the right margin. A tempo mark stands above the titles, flush with them, or beside
   the mark when there is no title, and the block is centred on the height of the frame of
   the mark. The part is exported again, measured and corrected up to four times, because
   MuseScore moves a tempo mark at a rehearsal mark on its own as well.
6. **Fit**: a text that ends past the right margin of the PDF and belongs to a system text,
   staff text or rehearsal mark gets a system break before its measure
   (`xsatz.mscz.break_before_text`), and the part is exported again. Then a part with more
   than two pages whose last page holds one or two systems, counted by their staff lines in
   the PDF, is exported again at 10 staff spaces instead of 12, and then at 8. When neither
   saves the page, it goes back to 12. A part with more than two pages is kept and reported with a
   warning. The finished PDF is copied to `<score> - <part>.pdf`.
7. **Finish** with the logo and accent rules of `xsatz.brand`, as for the full score.

The part style is the score style with the part defaults of MuseScore and these
differences: the top and bottom margins of the score, a running header with title and part
name, the copyright as a footer on page 1 only (`$C`), 5 mm above the bottom edge, every
text in EB Garamond, vendored as static fonts in `libs/font/garamond/`
([ADR 0004](0004-third-party-assets-in-libs.md)), a title of 20 pt that is not bold,
playing aids of 10 pt, rehearsal marks of 14 pt, tempo marks of 10 pt and 2 staff spaces
above the staff, MuseScore's default, bar numbers and multi-measure rest ranges enlarged by
the ratio of the staff sizes (1.75 / 1.085), and the largest system distance equal to the
smallest, so that every page of a part keeps the same distance. The staff size of 1.75 mm
is the same for every part and never changes to fit the pages.

The full score uses the same text font. Because MuseScore takes the font families of the
MusicXML over those of a style, the prepare stage of
[ADR 0008](0008-musescore-4-and-the-stages-around-it.md) writes the text font of the style
(`defaultFontFace`) into the defaults of the copy and drops the font families of single
texts (`xsatz.prepare`).

The render stage of the gate ([ADR 0007](0007-a-change-is-done-when-the-gate-is-green.md))
also renders the parts of the self-made fixture `tests/fixtures/dorico_like.musicxml` and
expects one PDF with at least one page per part.

## Consequences

Every part is set at the same readable size, gets the X-Satz title block and header and
fits on two pages where the system distance allows it. Rehearsal marks, tempi and playing
aids come from MuseScore's own part extraction and need no code in X-Satz.

EB Garamond has to be installed on every machine that renders, from the static files in
`libs/`. Without it MuseScore silently sets the texts in another font, and with only the
variable font installed it draws bold texts by thickening the regular weight. The full
score no longer uses Academico, the font of the Dorico originals. Placing the texts beside a rehearsal mark relies on reading them
back from the PDF, so a text the PDF holds in pieces or with unreadable glyphs is matched
by its readable characters, and a mark that is not found keeps MuseScore's stack.

A system break for a text at the margin costs room in that system, and a text that is too
long for a whole system still runs past the margin and is reported with a warning. The last
page of a part ends where its music ends instead of being spread to the bottom.

Every part has one of three system distances, 12, 10 or 8 staff spaces. Dense parts, in the
reference score the hi-hat and the toms, keep a third page. A tighter horizontal spacing or
smaller margins would be the next levers. They were not built.

Rendering the parts starts MuseScore at least three times, and once more for every round of
arranging and fitting. The reference score took about four minutes on the development
machine. The
JSON output of `--score-parts` and the style inside a part file are no documented interface
of MuseScore, so every MuseScore update is checked with the gate and by looking at the
parts. Tests cover the edits of the part files and the fitting with a stand-in for
MuseScore (`tests/test_mscz.py`, `tests/test_parts.py`).

Measuring the title block and the text under it by the outlines of their glyphs, which the
parts needed for their rule under the title block, also moves that rule in the full score of
the reference piece by 1.4 pt (0.5 mm).
