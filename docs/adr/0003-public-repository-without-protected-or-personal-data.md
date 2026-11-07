# 0003. The public repository holds no protected or personal data

Date: 2026-11-07

## Status

Accepted

## Context

The repository is public on GitHub. Two kinds of data must not appear in it:

- The arrangements X-Satz is developed and checked with are protected by copyright. They
  exist as Dorico projects, MusicXML and reference PDFs, and everything X-Satz generates from
  them (PDFs, images, MIDIs, excerpts) is protected as well. Anything committed is published
  and can hardly be removed from the git history again. At the same time these files are the
  benchmark for phase 1, so changing them by accident would make every comparison worthless.
- The scores carry personal and organisational information: arrangers, who adapted a piece,
  the band it is meant for, copyright lines and the logo of the band, later possibly contact
  data or credentials for other services. Written into code, styles or documentation, this
  information is published, has to be changed in code whenever it changes, and ties the tool
  to one band.

## Decision

We will keep protected and personal data out of the repository and let it reach X-Satz only
at run time.

Copyrighted scores:

- On development machines they live in `data/`, which `.gitignore` excludes. The package never
  refers to `data/` ([ADR 0005](0005-package-independent-of-locations.md)). The files in it
  are originals and are never modified. Results go to `data/out/`.
- A pre-commit hook rejects every file under `data/` and every file with the extensions `.pdf`,
  `.dorico`, `.mscz`, `.mscx`, `.mxl`, `.musicxml`, `.mid` or `.midi` outside `tests/fixtures/`.
  The CI runs the same hook on all files.
- Tests use only public domain or self-made fixtures with invented values.
- Documentation and ADRs describe scores and differences in words and figures. They
  name no titles, arrangers or other credits of the pieces and embed no images of them.

Personal and organisational data:

- The package, the shipped styles and the tests contain no names of people or organisations,
  no copyright lines, no logos, no contact data and no credentials. The documentation only
  says which band the project comes from.
- Texts of a piece, such as its title and credits, come from its MusicXML. Everything else
  comes from configuration: command line options and environment variables. The logo of the
  band lives outside the repository and is passed with `--logo` or `XSATZ_LOGO`, its accent
  colour with `--color` or `XSATZ_COLOR` as `#RRGGBB`. Without a colour X-Satz takes the
  accent colour of the logo.
- `.env` files and local configuration files are git-ignored, and a pre-commit hook rejects
  committed `.env` files. `.env.example` documents the keys with neutral placeholders.
- The command line reads a `.env` file from the directory it is started in, as most tools do.
  Variables already set in the environment and command line options win over it. The API
  never reads a file on its own and takes every value as an argument
  ([ADR 0005](0005-package-independent-of-locations.md)).

Package metadata in `pyproject.toml` (project name, authors, licence) is about the software,
not about the scores, and stays there.

## Consequences

The repository can be public without infringing rights, and another band can use X-Satz with
its own logo and credits without changing code.

Results of phase 1 can only be reproduced on machines that have the local files, and the
documentation shows no images of them. Without configuration a PDF has no logo. The hooks
only catch accidents: a renamed file extension or a name typed into the code is not
detected, so reviews have to look for both.
