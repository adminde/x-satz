# 0004. Third-party assets live unmodified in libs/

Date: 2026-11-07

## Status

Accepted

## Context

The reference scores set their text in Academico, a font Steinberg made for Dorico. MuseScore
takes fonts from the operating system, so every machine that renders, and later any server or
container, needs the font installed. Steinberg offers no standalone download. The font is
licensed under the SIL Open Font License 1.1 with the Reserved Font Name "Academico": it may be
redistributed with software as long as copyright notice and licence travel with it, and a
modified version must not be called Academico.

Fetching such files from wherever they happen to be found makes setups differ between machines
and leaves their origin and licence unclear. Fonts are not Python code and are not loaded by the
package itself, so they do not belong into `src/xsatz/`
([ADR 0005](0005-package-independent-of-locations.md)).

## Decision

We will keep third-party assets that X-Satz needs at run time but does not import as Python
code in `libs/`, as part of the repository:

- one directory per asset, `libs/<kind>/<name>/`, for example `libs/font/academico/`,
- the files exactly as published, never modified, renamed, subset or converted,
- the licence file of the asset next to it,
- only assets whose licence allows redistribution together with GPL software,
- every asset listed in `libs/README.md` with version, licence and source.

`libs/` is not part of the Python package. Developers install the fonts into the operating
system; a later container build copies them from `libs/`.

## Consequences

Every clone has the same font files with their licence, and their origin can be checked.
The repository grows by the size of the assets, about 250 KB for Academico.

`.gitattributes` marks `libs/**` as vendored and excludes it from line ending conversion, and the
pre-commit hooks that rewrite files skip `libs/`, so the files stay byte for byte as published.
The check for copyrighted scores still covers `libs/`.

A newer version of an asset replaces the old files as a whole and updates `libs/README.md`.
Differences between the vendored version and the one used for the reference PDFs (Academico
0.905 here, Dorico 5.1 for the references) may change text widths slightly. They were not measured.
