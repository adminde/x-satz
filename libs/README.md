# Third-party assets

Files that X-Satz needs at run time but does not import as Python code. They are kept exactly as
published, next to their licence ([ADR 0004](../docs/adr/0004-third-party-assets-in-libs.md)).
Do not modify, rename, subset or convert them.

| Asset | Path | Version | Licence | Source |
|---|---|---|---|---|
| Academico (Regular, Italic, Bold, Bold Italic) | `font/academico/` | 0.905 | SIL OFL 1.1, Reserved Font Name "Academico", see `COPYING` | Steinberg Media Technologies GmbH (copyright holder) |
| EB Garamond (static TTF, Regular to ExtraBold with italics) | `font/garamond/` | 1.003 | SIL OFL 1.1, see `OFL.txt` | The EB Garamond Project Authors, from the Google Fonts download (https://fonts.google.com/specimen/EB+Garamond) |

## Installing the fonts

MuseScore takes fonts from the operating system.

- Windows: select the `.otf` and `.ttf` files, right-click, "Install for all users".
- Linux: copy the `.otf` and `.ttf` files to `~/.local/share/fonts/` (or `/usr/local/share/fonts/`) and run
  `fc-cache -f`.
- macOS: open the `.otf` and `.ttf` files and click "Install".
