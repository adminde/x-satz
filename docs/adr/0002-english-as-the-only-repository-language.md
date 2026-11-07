# 0002. English as the only repository language

Date: 2026-11-07

## Status

Accepted

## Context

Python, MuseScore and their documentation are English. A repository that mixes languages forces
readers to switch within a single file, makes searching for a concept depend on guessing the
language, and leaves every author to choose the language anew.

The musical domain has terms whose English names are less common in band practice, such as
slide positions, valve combinations or rehearsal marks.

## Decision

We will use English as the only language in the repository. This covers code, identifiers,
comments, docstrings, tests, command line output and error messages, configuration, file and
folder names, documentation, READMEs, ADRs, commit messages, branch names, pull
request titles and descriptions.

Text that belongs to a score, such as titles, credits or instrument names in a MusicXML file,
is data and stays as it is.

## Consequences

Everything in the repository is readable with one vocabulary, and searching works without
guessing the language.

Domain terms need an agreed English name, used consistently: full score, part, playing aids
(valve combinations, slide positions, sticking), rehearsal mark, practice MIDI. There is no
automatic check for the language. Reviews have to check it.
