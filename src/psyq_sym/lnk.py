"""Decode the Psy-Q LNK object record stream (code chunks, patches, symbols, source-line records)."""

from __future__ import annotations

import struct
from dataclasses import dataclass


class LnkError(ValueError):
    """The bytes are not a record of the LNK grammar."""


@dataclass(frozen=True)
class Record:
    at: int
    kind: str
    args: tuple


def _u16(raw: bytes, i: int) -> int:
    return struct.unpack_from("<H", raw, i)[0]


def _u32(raw: bytes, i: int) -> int:
    return struct.unpack_from("<I", raw, i)[0]


def _name(raw: bytes, i: int) -> tuple[str, int]:
    length = raw[i]
    if i + 1 + length > len(raw):
        raise LnkError("name runs past the span")
    return raw[i + 1 : i + 1 + length].decode("latin1"), i + 1 + length


def expression(raw: bytes, i: int) -> tuple[tuple, int]:
    """One patch expression: constant, symbol index, section base, or the sum of two expressions."""
    op = raw[i]
    if op == 0x00:
        return ("const", _u32(raw, i + 1)), i + 5
    if op == 0x02:
        return ("sym", _u16(raw, i + 1)), i + 3
    if op == 0x04:
        return ("secbase", _u16(raw, i + 1)), i + 3
    if op == 0x2C:
        left, i = expression(raw, i + 1)
        right, i = expression(raw, i)
        return ("add", left, right), i
    raise LnkError(f"expression opcode {op:#x} at {i:#x}")


def record(raw: bytes, i: int) -> tuple[Record, int]:
    """The record at i and the offset after it. Patch offsets are relative to the code chunk before the patch."""
    op = raw[i]
    try:
        if op == 0x00:
            return Record(i, "end", ()), i + 1
        if op == 0x02:
            size = _u16(raw, i + 1)
            if i + 3 + size > len(raw):
                raise LnkError("code chunk runs past the span")
            return Record(i, "code", (raw[i + 3 : i + 3 + size],)), i + 3 + size
        if op == 0x06:
            return Record(i, "switch", (_u16(raw, i + 1),)), i + 3
        if op == 0x08:
            return Record(i, "bss", (_u32(raw, i + 1),)), i + 5
        if op == 0x0A:
            value, end = expression(raw, i + 4)
            return Record(i, "patch", (raw[i + 1], _u16(raw, i + 2), value)), end
        if op == 0x0C:
            name, end = _name(raw, i + 9)
            return Record(i, "xdef", (_u16(raw, i + 1), _u16(raw, i + 3), _u32(raw, i + 5), name)), end
        if op == 0x0E:
            name, end = _name(raw, i + 3)
            return Record(i, "xref", (_u16(raw, i + 1), name)), end
        if op == 0x10:
            name, end = _name(raw, i + 6)
            return Record(i, "section", (_u16(raw, i + 1), _u16(raw, i + 3), raw[i + 5], name)), end
        if op == 0x12:
            name, end = _name(raw, i + 7)
            return Record(i, "local", (_u16(raw, i + 1), _u32(raw, i + 3), name)), end
        if op == 0x1C:
            name, end = _name(raw, i + 3)
            return Record(i, "file", (_u16(raw, i + 1), name)), end
        if op == 0x32:
            return Record(i, "line_inc", (_u16(raw, i + 1), 1)), i + 3
        if op == 0x34:
            return Record(i, "line_inc", (_u16(raw, i + 1), raw[i + 3])), i + 4
        if op == 0x36:
            return Record(i, "line_inc", (_u16(raw, i + 1), _u16(raw, i + 3))), i + 5
        if op == 0x38:
            return Record(i, "line_set", (_u16(raw, i + 1), _u32(raw, i + 3))), i + 7
        if op == 0x3A:
            return Record(i, "line_set_file", (_u16(raw, i + 1), _u32(raw, i + 3), _u16(raw, i + 7))), i + 9
        if op == 0x3C:
            return Record(i, "line_end", (_u16(raw, i + 1),)), i + 3
    except (IndexError, struct.error) as error:
        raise LnkError(f"record {op:#x} at {i:#x} runs past the span") from error
    raise LnkError(f"opcode {op:#x} at {i:#x}")


def decode(raw: bytes, start: int = 0) -> tuple[list[Record], int]:
    """Records from start up to the first byte that is not a record, and the offset where decoding stopped."""
    records: list[Record] = []
    i = start
    while i < len(raw):
        try:
            rec, i = record(raw, i)
        except LnkError:
            break
        records.append(rec)
        if rec.kind == "end":
            break
    return records, i


def locate(raw: bytes, limit: int = 4096) -> tuple[int, list[Record], int]:
    """The start offset below limit from which the most bytes decode: (start, records, stop)."""
    best = max(range(min(limit, len(raw))), key=lambda k: (decode(raw, k)[1] - k, -k))
    records, stop = decode(raw, best)
    return best, records, stop
