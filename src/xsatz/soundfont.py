"""Shaped copies of SF2 SoundFonts for the audio export (ADR 0010).

Some SoundFonts swell into every note or fade it in on purpose, which makes short notes
sound late and soft. A shaped copy starts the samples later and shortens the fade-in. Only
sample headers and envelope generators change, so the copy has the size of the original.
"""

from __future__ import annotations

import array
import math
import struct
from dataclasses import dataclass
from pathlib import Path

# A cut never skips more of a sample than this, so that a slow swell keeps its attack.
MAX_CUT = 0.4
ATTACK = 34
INSTRUMENT, SAMPLE = 41, 53
LINKED = (2, 4)


@dataclass(frozen=True)
class Shaping:
    """How a copy of the SoundFont ``file`` differs from it.

    With ``swell`` every sample starts where it first reaches that share of its level. With
    ``fade_in`` no sound fades in longer than that many seconds.
    """

    file: Path
    swell: float | None = None
    fade_in: float | None = None

    def name(self) -> str:
        """The file name of the copy without extension, which MuseScore uses as its name."""
        parts = [self.file.stem]
        if self.swell is not None:
            parts.append(f"swell{round(self.swell * 100)}")
        if self.fade_in is not None:
            parts.append(f"fade{round(self.fade_in * 1000)}ms")
        return "-".join(parts)


@dataclass
class ShapeResult:
    target: Path
    samples_cut: int = 0
    fades_shortened: int = 0


class _Sf2:
    def __init__(self, data: bytearray):
        self.data = data
        self.chunks: dict[bytes, tuple[int, int]] = {}
        self._scan(12, len(data))

    def _scan(self, start: int, end: int) -> None:
        position = start
        while position + 8 <= end:
            tag = bytes(self.data[position : position + 4])
            size = struct.unpack("<I", self.data[position + 4 : position + 8])[0]
            if tag == b"LIST":
                self._scan(position + 12, position + 8 + size)
            else:
                self.chunks[tag] = (position + 8, size)
            position += 8 + size + (size & 1)

    def records(self, tag: bytes, fmt: str) -> list[tuple]:
        start, size = self.chunks[tag]
        width = struct.calcsize(fmt)
        return [
            struct.unpack(fmt, self.data[start + k : start + k + width])
            for k in range(0, size - width + 1, width)
        ]

    def put(self, tag: bytes, fmt: str, index: int, values: tuple) -> None:
        start, _ = self.chunks[tag]
        width = struct.calcsize(fmt)
        self.data[start + index * width : start + (index + 1) * width] = struct.pack(fmt, *values)


def _zones(sf2: _Sf2, presets: set[tuple[int, int]] | None) -> tuple[set[int], set[int]]:
    """Generator indices of the instrument zones and sample indices the presets use.

    Without ``presets`` every preset counts.
    """
    phdr = sf2.records(b"phdr", "<20sHHHIII")
    pbag, pgen = sf2.records(b"pbag", "<HH"), sf2.records(b"pgen", "<HH")
    inst, ibag, igen = (
        sf2.records(b"inst", "<20sH"),
        sf2.records(b"ibag", "<HH"),
        sf2.records(b"igen", "<HH"),
    )
    generators, samples = set(), set()
    for n, (_, program, bank, bag, *_rest) in enumerate(phdr[:-1]):
        if presets is not None and (bank, program) not in presets:
            continue
        for b in range(bag, phdr[n + 1][3]):
            for oper, amount in pgen[pbag[b][0] : pbag[b + 1][0]]:
                if oper != INSTRUMENT:
                    continue
                for zone in range(inst[amount][1], inst[amount + 1][1]):
                    for g in range(ibag[zone][0], ibag[zone + 1][0]):
                        generators.add(g)
                        if igen[g][0] == SAMPLE:
                            samples.add(igen[g][1])
    return generators, samples


def _cut(sf2: _Sf2, header: tuple, share: float) -> int:
    """Sample points to skip until the sample first reaches ``share`` of its first second."""
    _, start, end, _, _, rate, *_rest = header
    offset, _ = sf2.chunks[b"smpl"]
    head = array.array("h", sf2.data[offset + 2 * start : offset + 2 * min(end, start + rate)])
    window = max(1, rate // 200)
    levels = [max(map(abs, head[k : k + window])) for k in range(0, len(head) - window + 1, window)]
    if not levels or max(levels) == 0:
        return 0
    first = next(i for i, level in enumerate(levels) if level >= max(levels) * share)
    cut = min(first * window, int(rate * MAX_CUT))
    # Back to a zero crossing within 10 ms, so that the new start does not click.
    for back in range(cut, max(0, cut - rate // 100), -1):
        if back < len(head) and (head[back] == 0 or (head[back - 1] < 0) != (head[back] < 0)):
            return back
    return cut


def shape(
    shaping: Shaping, target: Path, presets: set[tuple[int, int]] | None = None
) -> ShapeResult:
    """Write the shaped copy of ``shaping.file`` to ``target`` for ``presets`` (bank, program).

    Linked stereo samples are cut alike, so that left and right stay together.
    """
    sf2 = _Sf2(bytearray(shaping.file.read_bytes()))
    generators, samples = _zones(sf2, presets)
    result = ShapeResult(target)
    if shaping.fade_in is not None:
        limit = round(1200 * math.log2(max(shaping.fade_in, 0.001)))
        for g, (oper, amount) in enumerate(sf2.records(b"igen", "<Hh")):
            if g in generators and oper == ATTACK and amount > limit:
                sf2.put(b"igen", "<Hh", g, (ATTACK, limit))
                result.fades_shortened += 1
    if shaping.swell is not None:
        headers = sf2.records(b"shdr", "<20sIIIIIBbHH")
        cuts: dict[int, int] = {}
        for index in sorted(samples):
            if index in cuts or index >= len(headers):
                continue
            cuts[index] = _cut(sf2, headers[index], shaping.swell)
            link, kind = headers[index][8], headers[index][9]
            if kind in LINKED and link < len(headers):
                cuts[link] = cuts[index]
        for index, cut in cuts.items():
            name, start, end, loop_start, loop_end, *rest = headers[index]
            if cut <= 0:
                continue
            new_start = min(start + cut, end - 1)
            sf2.put(
                b"shdr",
                "<20sIIIIIBbHH",
                index,
                (name, new_start, end, max(loop_start, new_start), loop_end, *rest),
            )
            result.samples_cut += 1
    target.write_bytes(sf2.data)
    return result
