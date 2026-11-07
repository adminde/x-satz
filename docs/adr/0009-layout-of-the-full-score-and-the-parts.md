# 0009. Layout of the full score and the parts

Date: 2026-11-07

## Status

Proposed

## Context

X-Satz engraves two kinds of documents from the same MusicXML: the full score for the
conductor and one part per instrument for the players. [ADR 0008](0008-musescore-4-and-the-stages-around-it.md)
decides how MuseScore is driven in stages. This record decides how the pages look, so that
full score and parts share one design and differ only where their use differs.

The full score follows the Dorico original: A4 landscape, a staff space of 1.085 mm, the page
and system breaks of the export and one system per page, which keeps the page count of the
original. Its title block, running header and footer follow the X-Satz design instead of
Dorico's credits.

A part should give a player at most two pages, which fit side by side on a music stand, but
it must stay readable. The maintainer decided that the staff size of a part never shrinks to
reach two pages. Only the distance between the systems may shrink, and only in an emergency:
the systems keep 12 staff spaces, and move to 10 and then to 8 only when that saves a third
page that would hold just one or two systems. Parts with a different distance each, chosen as
the largest that fits, looked uneven next to each other.

Findings with MuseScore 4.7.6 and the reference score:

- `--score-parts SCORE.mscz` prints a JSON document with the names of the parts and one
  MuseScore file per part, encoded in base64. `-P` exports nothing for a score imported from
  MusicXML, because such a score holds no parts yet.
- The parts take the style of the score with the part defaults of MuseScore: A4 portrait,
  a staff space of 1.75 mm, margins of 15 mm and multi-measure rests.
- The page and system breaks of the score do not reach the parts, so every part is laid out
  anew. Rehearsal marks, tempi, section titles and the playing aids appear in every part.
- Every part file carries a style of its own inside the score entry. It wins over the
  `score_style.mss` of the file, so replacing that file alone changes nothing.
- The title frame is copied with the label of the full score, plus a small part name above
  the title. At portrait width a long title runs into the credit lines.
- The copyright frame of the full score is copied too. Without its page break it lands after
  the second system of page 1.
- MuseScore takes the font families of the MusicXML, those of the defaults and those written
  on single texts, over the fonts of a style. Dorico writes Academico into both.
- Academico, the text font of the Dorico originals, has no weight below Regular. In a part
  its texts looked heavy next to the airier Dorico score. Of the fonts tried, MuseScore did
  not find the weights of variable fonts and set the texts in Tahoma instead, Source Serif 4
  and Crimson Pro looked too modern, and the old style figures of Cormorant Garamond make a
  "1" look like an "I", which a playing aid cannot afford. EB Garamond, a classical serif
  that is lighter than Academico, has lining figures and a bold weight for the rehearsal
  marks.
- The rule under the title block of page 1 needs a gap between the title block and the
  first text of the music. The box of an italic part name reaches below its letters, so
  measured by boxes that gap vanished in five parts, and the rule was left out.
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
- MuseScore spreads the systems of a page that is not full. Page 1 of a part is full because
  of the title block, page 2 is not, so the systems stood visibly further apart on page 2.
- With the part defaults, 4 of the 10 parts of the reference score had three pages. The
  hi-hat part has about 27 systems, 10 to 12 fit on a page even at 4 staff spaces, so no
  distance brings it down to two pages at this staff size.

Options that were weighed: one MusicXML per part through the full score pipeline would need
X-Satz to copy rehearsal marks, tempi and section titles into every part, which Dorico
writes into the top part only. Shrinking the staff size of a part step by step was the first
plan and was rejected by the maintainer in favour of readability.

## Decision

We will lay out both documents with two styles that ship with the package,
`src/xsatz/styles/score.mss` for the full score and `src/xsatz/styles/part.mss` for the
parts, and with the same design.

Shared by full score and parts:

- Every text is set in EB Garamond, vendored as static fonts in `libs/font/garamond/`
  ([ADR 0004](0004-third-party-assets-in-libs.md)). The prepare stage writes the text font of
  the style (`defaultFontFace`) into the defaults of the copy and drops the font families of
  single texts (`xsatz.prepare`), the parts also drop those MuseScore wrote into their texts.
- Page 1 carries the title block: the logo left of the centred title, the label on the left
  ("full score" from the MusicXML, the part name in a part), the credit lines on the right
  and a rule in the accent colour under the block. The copyright stands on page 1 only, 5 mm
  above the bottom edge.
- Every following page carries a running header with the logo, the title, in a part also
  the part name, the page number as `page / pages` and a rule in the accent colour under it.
- Logo and rules are stamped into the finished PDF by `xsatz.theme`. Texts are measured by
  the outlines of their glyphs, so the rule under the title block finds its room.

The full score:

- A4 landscape, the margins of the style written into the copy, a staff space of 1.085 mm,
  the page and system breaks of the export, no multi-measure rests.
- The copyright stands in a frame after the system of page 1
  ([ADR 0008](0008-musescore-4-and-the-stages-around-it.md)).

The parts, rendered with `xsatz parts` (`xsatz.parts`) in these stages:

1. **Prepare and import** the MusicXML with the score style, as for the full score, without
   the copyright frame.
2. **Extract**: `--score-parts` gives one MuseScore file per part.
3. **Edit** every part (`xsatz.mscz.edit_part`): remove its own style and the font families
   in its texts, put the part style in place, write the part name as label of the title
   block, remove MuseScore's small part name and make the title frame tall enough for the
   title above the credit lines.
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
   saves the page, it goes back to 12. A part with more than two pages is kept and reported
   with a warning. The finished PDF is copied to `<score> - <part>.pdf`.
7. **Finish** with the logo and the rules, as for the full score.

The part style is the score style with these differences: A4 portrait, the left and right
margins of MuseScore's parts and the top and bottom margins of the score, a staff space of
1.75 mm for every part that never changes to fit the pages, multi-measure rests, a title of
20 pt that is not bold, playing aids of 10 pt, rehearsal marks of 14 pt, tempo marks of 10 pt
and 2 staff spaces above the staff, MuseScore's default, bar numbers and multi-measure rest
ranges enlarged by the ratio of the staff sizes (1.75 / 1.085), the copyright as a footer
on page 1 only (`$C`), and 12 staff spaces between the systems, the largest distance equal
to the smallest, so that every page of a part keeps the same distance.

The render stage of the gate ([ADR 0007](0007-a-change-is-done-when-the-gate-is-green.md))
renders the full score of the public domain fixture and the parts of the self-made fixture
`tests/fixtures/dorico_like.musicxml` and expects one PDF with at least one page each.

## Consequences

Full score and parts look like one edition: same font, same title block and header, same
accent colour. Every part is set at the same readable size and fits on two pages where the
emergency distances allow it. Rehearsal marks, tempi and playing aids come from MuseScore's
own part extraction and need no code in X-Satz.

EB Garamond has to be installed on every machine that renders, from the static files in
`libs/`. Without it MuseScore silently sets the texts in another font, and with only the
variable font installed it draws bold texts by thickening the regular weight. The full
score no longer uses Academico, the font of the Dorico originals, so comparisons with the
reference differ in the texts.

Placing the texts beside a rehearsal mark relies on reading them back from the PDF, so a
text the PDF holds in pieces or with unreadable glyphs is matched by its readable
characters, and a mark that is not found keeps MuseScore's stack. A system break for a text
at the margin costs room in that system, and a text that is too long for a whole system
still runs past the margin and is reported with a warning. The last page of a part ends
where its music ends instead of being spread to the bottom.

Every part has one of three system distances, 12, 10 or 8 staff spaces. Dense parts, in the
reference score the hi-hat and the toms, keep a third page. A tighter horizontal spacing or
smaller margins would be the next levers. They were not built.

Rendering the parts starts MuseScore at least three times, and once more for every round of
arranging and fitting. The reference score took about four minutes on the development
machine. The JSON output of `--score-parts` and the style inside a part file are no
documented interface of MuseScore, so every MuseScore update is checked with the gate and by
looking at the pages. Tests cover the edits of the part files, the placement beside the
marks and the fitting with a stand-in for MuseScore (`tests/test_mscz.py`,
`tests/test_parts.py`).

Measuring the title block and the text under it by the outlines of their glyphs also moves
the rule under the title block of the full score of the reference piece by 1.4 pt (0.5 mm).
