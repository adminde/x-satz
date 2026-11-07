# 0005. The package is independent of locations

Date: 2026-11-07

## Status

Accepted

## Context

The core runs on development machines, and later possibly on a server or inside another
application, where input files sit in arbitrary folders. Defaults such as `output/` or `input/`
relative to the working directory only work when the program is started from the repository
root, silently write files somewhere else otherwise, and tie the package to a folder layout that
exists only in this repository.

During development, copyrighted scores are needed as test material. They must not become part
of the package or the repository ([ADR 0003](0003-public-repository-without-protected-or-personal-data.md)).

## Decision

We will keep the package free of locations:

- Every input file or directory is passed in explicitly, as a function argument or on the
  command line.
- Output directories are optional. Without one, results go next to the input: `render` writes
  into the directory of the MusicXML file, `compare` into `<new PDF stem>-compare/` next to the
  generated PDF.
- The package contains no paths relative to the repository or the working directory.
  Resources that ship with X-Satz, such as MuseScore styles, live inside the package
  (`src/xsatz/styles/`) and are loaded with `importlib.resources`.
- Local development data lives in the git-ignored `data/` folder and is only ever passed in.

## Consequences

The CLI and the API behave the same no matter where they are started, and any caller can hand
over any path. Styles are installed together with the package.

Without `--out`, `render` writes next to the source. For files in `data/`, developers therefore
pass `--out data/out` so that the originals' folders stay clean. Tests check the defaults of
`render` and `compare`.
