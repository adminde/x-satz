# Architecture decision records

These records explain *why* X-Satz is built the way it is. Each one describes a single
decision with its context, the decision and its consequences, following Michael Nygard's
format (see [0000-template.md](0000-template.md)).

## When to write one

When a decision is hard to reverse or binds later work, for example:

- a new runtime dependency or external program,
- a change to the layers, the data flow or the public API of the core,
- choosing between style adjustments and MusicXML preprocessing for a whole class of problems,
- a new rule for everyone (language, file locations, tools, CI),
- a rule that pre-commit, the gate or a test enforces from then on.

No ADR for single style values or bug fixes. Findings from experiments go into the context
of the record whose decision they support.

## Process

1. Copy the template to `docs/adr/NNNN-short-title.md`, using the next free four digit number
   and a lower case ASCII file name with hyphens. Numbers are never reused.
2. Set the status to **Proposed**, set the date, fill in context, decision and consequences.
3. Add it to the index below. The record goes into the same branch as the change it
   justifies, or into an earlier one.
4. The maintainer decides: **Accepted** or **Rejected**. An accepted record gets the date of
   its acceptance. Rejected records stay in place.
5. Accepted records are not changed in substance. If the decision changes, a new record
   supersedes the old one, whose status becomes "Superseded by [ADR NNNN](…)". Fixing typos
   and broken links is fine.

## Index

| No. | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-english-as-the-only-repository-language.md) | English as the only repository language | Accepted |
| [0003](0003-public-repository-without-protected-or-personal-data.md) | The public repository holds no protected or personal data | Accepted |
| [0004](0004-third-party-assets-in-libs.md) | Third-party assets live unmodified in libs/ | Accepted |
| [0005](0005-package-independent-of-locations.md) | The package is independent of locations | Accepted |
| [0006](0006-pip-ruff-pre-commit-and-github-actions.md) | pip, Ruff, pre-commit and GitHub Actions | Accepted |
| [0007](0007-a-change-is-done-when-the-gate-is-green.md) | A change is done when the gate is green | Accepted |
| [0008](0008-musescore-4-and-the-stages-around-it.md) | MuseScore 4 engraves, X-Satz works in stages around it | Accepted |
| [0009](0009-layout-of-the-full-score-and-the-parts.md) | Layout of the full score and the parts | Proposed |
| [0010](0010-practice-files-play-the-score.md) | Practice files play the score as written unless the band configures them | Proposed |
