# 0010. Practice files play the score as written unless the band configures them

Date: 2026-11-08

## Status

Proposed

## Context

Phase 3 produces practice MIDIs from the same MusicXML export the scores are engraved from,
so that the musical director exports a piece only once. For the reference piece he also
exported a second version, made only for playback. Comparing the two exports measure by
measure, with the pitches compared through MuseScore's MIDI export of both, showed:

- Every pitch of the trumpets, trombones and euphonium is one whole tone lower in the
  playback version, every pitch of the sousaphone a major ninth lower. Clefs and
  transpositions are the same in both, the key signature moves from three to five flats.
  The brass of the band are B flat instruments that read in C. Dorico exports them as
  instruments in C, so MuseScore plays them a whole tone too high, and the sousaphone also
  sounds one octave below the octave Dorico exports.
- The playback version has one bar more before the first bar. In it a hi-hat and an
  additional part of body percussion play two half notes, and in the first bar, which is
  silent up to the pickup on the second half of beat 4, both play four quarters. That is
  the count-in "1 – 2 – 1 2 3 4". The bar numbers and the rehearsal marks, which show bar
  numbers, are shifted by one. Tempo and rehearsal mark of the first bar sit in the added bar.
- In bar 50 the playback version has a forte in the first trumpet and a piano in all other
  parts that play there. The engraving version has no dynamic there.
- Everything else that differs is engraving: stem directions, tie directions and lyric
  extenders that follow from the transposition, and the credits.

Two audio files the director exported from Dorico for an older version of the piece, a
full mix and a practice mix for one trumpet, were read without decoding, from the gain and
the size of every MP3 frame. Both count in with "1 – 2 – 1 2 3 4" at 0, 1.1, 2.2, 2.8, 3.3
and 3.9 seconds, at 108 beats per minute, and the clicks are about as loud as the music.
The practice mix is a little quieter than the full mix as a whole, as it is when the other
parts are turned down.

What was not collected: the director's own MIDI files, the balance of his practice mix in
decibels, which would need a decoded signal, and whether the dynamics of bar 50 belong into
the engraved score as well.

MuseScore 4.7.6 on the command line, tested with the reference piece:

- `-o PIECE.mid` writes a MIDI file of format 1 with one track per staff, in the order of
  the parts, at the sounding pitch of the transpositions, with velocities from the dynamics,
  rehearsal marks as markers and the playing aids as lyric events. All percussion parts
  share channel 10.
- A transposition in the MusicXML copy makes MuseScore play the director's pitches: with a
  whole tone down for the brass and a ninth for the sousaphone, the MIDI of the engraving
  export has the same notes at the same times as the MIDI of the playback export.
- The drum keys of the kit entries of [ADR 0008](0008-musescore-4-and-the-stages-around-it.md)
  reach the MIDI unchanged, so a hi-hat played as a bass drum. Notes of a single percussion
  instrument that name no instrument are played at the key of their staff position, the
  bass drum of the reference piece as a low conga. With General MIDI keys in the copy and
  the instrument named on every note, MuseScore plays General MIDI drum sounds.
- `-o PIECE.mp3` and `.wav` render with the sound font MS Basic, which ships with MuseScore
  under the MIT licence, in about 12 seconds for the reference piece. The volumes of the
  mixer in `audiosettings.json` inside the `.mscz` reach the audio export, but not the
  MIDI export. MuseSounds are not installed on the development machine and are not free
  software.
- At MuseScore's default dynamic the hand clap of MS Basic peaks about 14 dB below the peaks
  of the band, and a listener did not hear the count-in. Of eight short sounds rendered as
  count-in, the maintainer chose the sticks. At forte they peak at the level of the band,
  at fortississimo they clip.
- MS Basic follows velocity a little more steeply than the square of General MIDI players:
  whole notes of a trumpet and a tuba at mezzoforte, piano, pianissimo and pianississimo
  (velocities 80, 49, 33 and 16) sounded 0, 10, 18 and 31 dB apart. Other parts 6 dB softer
  in an audio practice mix were too little contrast for the maintainer.
- Every part sends 30 % to MuseScore's built-in reverb unless the file says otherwise.
  Rendered without the send, the trumpet of the reference piece lost 0.7 dB.
- `audiosettings.json` also chooses the sound of a part: a SoundFont by its file name
  without extension, one of its presets as `name\bank\program`. MuseScore finds SoundFonts
  in its own sound folder and in the SoundFont folder of the user. For an unknown name it
  plays MS Basic without a warning. The presets of MS Basic marked "Expr." stayed almost
  silent when chosen this way.
- A conversion job (`-j`) with MP3 exports crashed MuseScore. Every MP3 takes a run of its
  own.

Free sound libraries were compared by ear with the reference piece, the maintainer judging:

- MuseScore_General_Full (MIT), the full version of the font MS Basic was cut from, played
  the trumpet nearly sample for sample like MS Basic.
- GeneralUser GS 2.0 (a licence of its own that allows music production) sounded different
  but was not preferred.
- VSCO 2 Community Edition (CC0) has trumpet, trombone and tuba as SFZ, which MuseScore 4
  plays only through a plugin. Rendered with sfizz_render (BSD-2) and mixed outside of
  MuseScore, it was not preferred either.
- The brass of the Sonatina Symphonic Orchestra (SF2, Creative Commons Sampling Plus 1.0)
  was preferred over MS Basic. Its presets do not follow General MIDI: trumpet solo is
  program 27, tenor trombone 31, horn 29 and tuba 34. It has no euphonium, and its
  percussion is an orchestral set with no hi-hat or toms and keys of its own, so the drum
  parts stay with MS Basic.
- MuseSounds are not free software and were not tried.
- The maintainer preferred Sonatina with every sample starting where it reaches half its
  level and the horn without its fade-in. Without the cut the swell came back and was
  judged worse. Sonatina's solo trumpet sounded bad on short loud notes from B3 to C♯4,
  which trumpet 3 plays from bar 44 on, MS Basic sounded worse elsewhere, and Sonatina's
  trumpet section without its fade-in was the compromise for that part.
- With the solo trombone of Sonatina both trombones sounded quacking from bar 44 on, each
  of them alone did not. Before bar 44 they never play the same note, from bar 44 to 76 24
  of their 42 common notes are unisons. Two copies of one sample at one pitch add up
  exactly: two trumpets in unison sounded 6 dB louder than one, where two players add
  about 3 dB, and the copies cancel each other in part. The trombone section of Sonatina,
  a recording of several players, hid it better. In the reference piece trumpets 2 and 3
  share 56 notes, trombones 1 and 2 share 29.
- A colour on a MusicXML note reaches the note in MuseScore's file, and MuseScore leaves a
  note marked `<play>0</play>` out of the audio and the MIDI export. With the second
  trumpet muted that way, the unison sounded like the first trumpet alone.
- Measured over the bars a part plays, Sonatina's solo trombone, trombone section, tuba and
  horn sound 6, 5, 5 and 9 dB softer than the trombone and tuba MS Basic plays for these
  parts, its trumpet about as loud. MuseScore applies mixer volumes above 0 dB exactly,
  +15 dB was tried. Raising Sonatina's trombones, tuba and horn by 6, 5 and 9 dB made the
  loud end of the reference piece distort, and the maintainer took it back.
- MuseScore mixes the whole band of the reference piece above full scale at its loud end:
  the full mix peaked at 2.4 times full scale with MS Basic and at 1.8 times with
  Sonatina, from about bar 70 on. The master volume in `audiosettings.json` lowers the whole
  mix exactly, −8 dB was tried.
- Sonatina's brass swell into a note. A separate quarter at mezzoforte reached 90 % of its
  level after 240 ms on the trumpet, 705 ms on the solo trombone and on the tuba, against
  55, 220 and 95 ms with MS Basic. At 160 beats per minute an eighth lasts 190 ms. The
  swell is part of the recordings, except for the horn: Sonatina gives its solo horn a
  fade-in of 0.6 s in the volume envelope of the SoundFont, and its trumpet section 0.25 s.

The maintainer decided that X-Satz plays a score as written by default: no transposition,
no count-in, MS Basic. Everything that turned the engraving export into the director's
playback is a setting of the band.

## Decision

We will write practice files with `xsatz audio`, implemented in `xsatz.audio`, in these
stages:

1. **Prepare** the copy of the MusicXML as for the engraving
   ([ADR 0008](0008-musescore-4-and-the-stages-around-it.md)), then make it the playback
   copy (`xsatz.sounds`):
   - mark the notes that parts with the same samples play in unison, with the same start,
     pitch and length, ties included, by a colour per group (`xsatz.sounds.tag_unisons`),
   - always give every percussion entry the General MIDI key of its instrument sound, its
     notehead and, for an open or half open hi-hat, its technical mark, order rack and floor
     toms by their staff position, let an instrument without a sound clap, and name the
     instrument on every note of a single percussion instrument,
   - add the semitones of the settings to the transposition of a pitched part, chosen by
     the start of its MusicXML instrument sound,
   - when the settings ask for one, add a count-in part that ticks "1 – 2 – 1 2 3 4" on a
     General MIDI drum key at a dynamic of the settings: one bar of clicks on every second
     beat before the first bar, then clicks on the beats of the first bar up to the first
     note of a pitched part. When the music starts on the first beat, the count-in has two
     bars of its own. The added bars are not counted, so bar numbers stay those of the
     parts, and the first one carries the tempo of the first bar.
2. **Import** the sounding copy with MuseScore into its own file.
3. **MP3s**: the edit stage writes sound, volume and reverb of every part into
   `audiosettings.json` (`xsatz.mscz.set_audio`), and MuseScore exports `<score>.mp3` and
   every `<score> - <part>.mp3` in a run of its own, at 256 kbit/s like the director's
   exports. In a practice MP3 the other parts except the count-in play the configured
   decibels softer, 15 dB by default. Of every unison group only one part plays
   (`xsatz.mscz.play_unisons_once`): in a practice MP3 the own part, else the first part.
   Before the MP3s the full mix is rendered once as WAV, and every MP3 of the piece gets
   the master volume that brings the peak of the full mix to −1 dB below full scale, or
   0 dB when it peaks lower. Full mix and practice files keep their level against each
   other.
   A sound with `swell` or `fade_in` is played from a copy of `<soundfont>.sf2` that
   `xsatz.soundfont` writes into the SoundFont folder: every sample of the presets in use
   starts where it first
   reaches the configured share of its level, at most 0.4 s later and at a zero crossing,
   and no fade-in of the volume envelope lasts longer than configured. Only sample headers
   and envelope generators change. The copy is written again when the original is newer.
4. **MIDIs**, with `--midi`: MuseScore exports `<score>.mid`, and every
   `<score> - <part>.mid` is a copy in which the note velocities of all other parts except
   the count-in are scaled to sound the configured decibels softer in a General MIDI player,
   by the factor 10^(−dB/40). The director needs the MP3s, the MIDIs are for players who
   practise with a MIDI player.

The settings come from the section `[audio]` of `x-satz.conf`
([ADR 0003](0003-public-repository-without-protected-or-personal-data.md)) and reach the
package as `AudioSettings` ([ADR 0005](0005-package-independent-of-locations.md)):
`softer`, `reverb`, `count_in` with `key` and `dynamic`, `transpose` with semitones and
`sounds` with `soundfont`, `bank`, `program`, `swell` and `fade_in`, `sounds.parts` with the
same keys for a single part by part name, and `soundfont_dir`. A part name is local to
the band like every setting. Transpositions and sounds are nested
tables by the parts of the MusicXML instrument sound, `[audio.transpose.brass]` with
`trumpet = -2` for every sound that starts with `brass.trumpet`, and the most specific
entry wins. A family in `[audio.sounds]` passes all its keys but the program on to its
instruments, which may change them. When it has instruments of its own and no program, it
is no sound itself, because the automatic choice of a SoundFont without General MIDI
programs can be silent. No MusicXML instrument sound starts with `parts`, so the key
cannot clash with an instrument.
`x-satz.example.conf` holds the playback worked out here: brass a whole tone lower and the
tuba a ninth, a count-in of sticks at forte, the brass of the Sonatina Symphonic Orchestra
shaped with `swell = 0.5` and `fade_in = 0.01`, and its trumpet section for trumpet 3.

The dynamics that the playback version has and the engraving version lacks are not
derived. They belong into the score the director exports.

The render stage of the gate ([ADR 0007](0007-a-change-is-done-when-the-gate-is-green.md))
also writes the MIDIs of the self-made fixture `tests/fixtures/dorico_like.musicxml` and
expects one practice MIDI per part.

## Consequences

The director exports a piece once. Without settings the files sound as the score is
written, and a band whose brass play in B flat gets its own pitches from the example
settings. Another band writes its own table.

The practice MIDIs need one MuseScore run in total, because the copies are made from the
MIDI file of the band. Lower velocities change loudness and timbre of most SoundFonts. A MIDI player
can also mute or solo tracks, but the three percussion tracks share one channel. The MP3s
need one run for the import, one for the WAV that measures the peak and one run per
file, about 12 seconds each for the reference piece.

X-Satz ships no SoundFont. MS Basic comes with MuseScore. Local SoundFonts may lie in
the git-ignored `libs/sounds/`, an exception to
[ADR 0004](0004-third-party-assets-in-libs.md), listed in `libs/README.md`. A SoundFont named in the settings
has to be installed in MuseScore's SoundFont folder on every machine that renders, and a
missing one is not reported: MuseScore plays MS Basic instead. The Sonatina Symphonic
Orchestra of the example settings is free to use for music, also commercially, but its
licence is no free software licence. It is a choice of the band, not a dependency of
X-Satz. `audiosettings.json` is no documented interface of MuseScore, so every update is
checked by listening.

A unison of parts with the same samples sounds as one part, about 3 dB softer than two
players. The MIDIs keep every note, and Sonatina still swells into short notes. The settings are not checked
against the instrument sounds of a score, so a key that never matches is silently without
effect. TOML cannot give a family and one of its instruments
a transposition each, `brass = -2` beside `brass.tuba`, so the example names every
instrument. Tests cover the sounding copy
(`tests/test_sounds.py`), the settings (`tests/test_config.py`), the mixer edit
(`tests/test_mscz.py`) and the practice files with a stand-in for MuseScore
(`tests/test_audio.py`).
