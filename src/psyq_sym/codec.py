"""Psy-Q SYM records, including fragments retained inside ROM images.

Addresses precede tags, never follow names. The journal's dbgfuncs.py supplied
our discovery pattern; decoding the complete record fixes its one-record shift.
COFF type modifiers are ordered outermost first. Offsets/sizes remain raw SYM
values (bitfields use bits); anonymous tags must not be guessed into C names.
"""

from __future__ import annotations

import re
import struct
from typing import Any

_CLASSES = {
    0: "null",
    1: "auto",
    2: "external",
    3: "static",
    4: "register",
    5: "external_definition",
    6: "label",
    7: "undefined_label",
    8: "struct_member",
    9: "argument",
    10: "struct_tag",
    11: "union_member",
    12: "union_tag",
    13: "typedef",
    14: "undefined_static",
    15: "enum_tag",
    16: "enum_member",
    17: "register_argument",
    18: "bitfield",
    100: "block",
    101: "function",
    102: "end_struct",
    103: "file",
    104: "line",
    105: "alias",
    106: "hidden",
}
_BASE = (
    "null",
    "void",
    "char",
    "short",
    "int",
    "long",
    "float",
    "double",
    "struct",
    "union",
    "enum",
    "enum_member",
    "unsigned char",
    "unsigned short",
    "unsigned int",
    "unsigned long",
)
_NAME = re.compile(r"[A-Za-z_.$][\w.$]*\Z", re.ASCII)
_TAGS = re.compile(rb"[\x80\x82\x84\x86\x88\x8a\x8c\x8e\x90\x92\x94\x96\x9c]")


class DecodeError(ValueError):
    """Invalid or truncated record; callers may explicitly resynchronise."""


def decode(data: bytes, offset: int = 0, end: int | None = None) -> dict[str, Any]:
    """Decode one complete record at offset, without reading past exclusive end."""
    limit = len(data) if end is None else end
    if not 0 <= offset < limit <= len(data):
        raise DecodeError("invalid range")
    pos = offset

    def read(fmt: str) -> tuple[Any, ...]:
        nonlocal pos
        size = struct.calcsize("<" + fmt)
        if pos + size > limit:
            raise DecodeError(f"truncated record at {offset:#x}")
        values = struct.unpack_from("<" + fmt, data, pos)
        pos += size
        return values

    def string() -> str:
        nonlocal pos
        size = read("B")[0]
        if pos + size > limit:
            raise DecodeError(f"truncated string at {pos:#x}")
        raw = data[pos : pos + size]
        pos += size
        if any(c < 32 or c > 126 for c in raw):
            raise DecodeError("non-printable name")
        return raw.decode("ascii")

    address, tag = read("IB")
    row: dict[str, Any] = {"offset": offset, "address": address, "tag": tag}
    if tag in (0x8C, 0x9C):
        values = read("HIHIi")
        row.update(
            zip(
                ("frame_register", "frame_size", "return_register", "register_mask", "mask_offset"), values, strict=True
            )
        )
        if tag == 0x9C:
            row.update(zip(("float_register_mask", "float_mask_offset"), read("Ii"), strict=True))
        row["line"] = read("I")[0]
        row.update(kind="function_start", file=string(), name=string())
        if row["frame_register"] > 31 or row["return_register"] > 31 or not _NAME.fullmatch(row["name"]):
            raise DecodeError("invalid function")
    elif tag in (0x94, 0x96):
        storage, typ, size = read("HHI")
        if storage not in _CLASSES:
            raise DecodeError("unknown COFF storage class")
        row.update(kind=_CLASSES[storage], storage_class=storage, type_code=typ, size=size)
        dims, type_tag = [], ""
        if tag == 0x96:
            count = read("H")[0]
            if count > 6 or count > (limit - pos) // 4:
                raise DecodeError("truncated dimensions")
            dims = list(read("I" * count))
            type_tag = string()
        name = string()
        if not _NAME.fullmatch(name) or (type_tag and not _NAME.fullmatch(type_tag)):
            raise DecodeError("invalid symbol name")
        modifiers, rest = [], typ >> 4
        while rest:
            mod = rest & 3
            if mod:
                modifiers.append(("", "pointer", "function", "array")[mod])
            rest >>= 2
        row.update(
            name=name, type={"base": _BASE[typ & 15], "modifiers": modifiers, "tag": type_tag, "dimensions": dims}
        )
    elif tag == 0x88:
        row.update(kind="file", line=read("I")[0], file=string())
    elif tag in (0x86, 0x8E, 0x90, 0x92):
        row.update(
            kind={0x86: "line", 0x8E: "function_end", 0x90: "block_start", 0x92: "block_end"}[tag], line=read("I")[0]
        )
    elif tag in (0x80, 0x82, 0x84):
        row.update(kind="line_delta", delta=1 if tag == 0x80 else read("B" if tag == 0x82 else "H")[0])
    elif tag == 0x8A:
        row.update(kind="line_end")
    else:
        raise DecodeError(f"unsupported tag {tag:#x}")
    row["end"] = pos
    return row


def scan(data: bytes, start: int, end: int) -> dict[str, Any]:
    """Recover contiguous runs, retaining only runs of 3+ records with a named anchor.

    Gaps are explicit; recovered fragments do not imply a complete symbol file.
    A standalone byte-pattern match cannot establish a type or function.
    """
    if not 0 <= start < end <= len(data):
        raise DecodeError("invalid ROM range")
    records: list[dict[str, Any]] = []
    runs: list[dict[str, int]] = []
    cursor = start
    for match in _TAGS.finditer(data, start + 4, end):
        pos = match.start() - 4
        if pos < cursor:
            continue
        run = []
        while pos < end:
            try:
                row = decode(data, pos, end)
            except DecodeError:
                break
            run.append(row)
            pos = row["end"]
        if len(run) < 3 or not any(r.get("name") for r in run):
            continue
        runs.append({"start": run[0]["offset"], "end": pos, "records": len(run)})
        records.extend(run)
        cursor = pos
    gaps, pos = [], start
    for run in runs:
        if pos < run["start"]:
            gaps.append({"start": pos, "end": run["start"]})
        pos = run["end"]
    if pos < end:
        gaps.append({"start": pos, "end": end})
    types = []
    active = None
    for row in records:
        if row["kind"] in ("struct_tag", "union_tag", "enum_tag"):
            active = {**row, "members": [], "complete": False}
            types.append(active)
        elif active and row["kind"] in ("struct_member", "union_member", "enum_member", "bitfield"):
            previous = active["members"][-1] if active["members"] else active
            if previous["end"] != row["offset"]:
                active = None
            else:
                active["members"].append(row)
        elif row["kind"] == "end_struct" and active:
            previous = active["members"][-1] if active["members"] else active
            active["complete"] = row["name"] == ".eos" and previous["end"] == row["offset"]
            active = None
        elif active:
            active = None
    return {"start": start, "end": end, "runs": runs, "gaps": gaps, "records": records, "types": types}
