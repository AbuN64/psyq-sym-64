"""Psy-Q DUMPSYM spelling for records supported by the pinned Go oracle."""

from __future__ import annotations

from typing import Any

from psyq_sym.codec import decode

_CLASSES = {
    1: "AUTO",
    2: "EXT",
    3: "STAT",
    4: "REG",
    6: "LABEL",
    8: "MOS",
    9: "ARG",
    10: "STRTAG",
    11: "MOU",
    12: "UNTAG",
    13: "TPDEF",
    15: "ENTAG",
    16: "MOE",
    17: "REGPARM",
    18: "FIELD",
    102: "EOS",
}
_BASE = (
    "NULL",
    "VOID",
    "CHAR",
    "SHORT",
    "INT",
    "LONG",
    "FLOAT",
    "DOUBLE",
    "STRUCT",
    "UNION",
    "ENUM",
    "MOE",
    "UCHAR",
    "USHORT",
    "UINT",
    "ULONG",
)


def body(row: dict[str, Any]) -> str:
    tag = row["tag"]
    if tag in (0x94, 0x96):
        typ = row["type"]
        parts = [{"pointer": "PTR", "function": "FCN", "array": "ARY"}[m] for m in typ["modifiers"]]
        parts.append(_BASE[row["type_code"] & 15])
        storage = _CLASSES.get(row["storage_class"], f"Class({row['storage_class']})")
        result = f"Def{'2' if tag == 0x96 else ''} class {storage} type {' '.join(parts)} size {row['size']}"
        if tag == 0x96:
            dims = " ".join(map(str, [len(typ["dimensions"]), *typ["dimensions"]]))
            result += f" dims {dims} tag {typ['tag']}"
        return result + f" name {row['name']}"
    if tag == 0x8C:
        fields = [
            ("fp", row["frame_register"]),
            ("fsize", row["frame_size"]),
            ("retreg", row["return_register"]),
            ("mask", f"${row['register_mask']:08x}"),
            ("maskoffs", row["mask_offset"]),
            ("line", row["line"]),
            ("file", row["file"]),
            ("name", row["name"]),
        ]
        return "Function_start" + "".join(f"\n    {key} = {value}" for key, value in fields)
    if tag == 0x88:
        return f"Set SLD to line {row['line']} of file {row['file']}"
    if tag in (0x86, 0x8E, 0x90, 0x92):
        return {
            0x86: "Set SLD linenum to ",
            0x8E: "Function_end   line ",
            0x90: "Block_start  line = ",
            0x92: "Block_end  line = ",
        }[tag] + str(row["line"])
    if tag == 0x8A:
        return "End SLD info"
    raise ValueError(f"tag {tag:#x} has no oracle dump implementation")


def dump(data: bytes) -> str:
    """Dump a complete MND envelope; used for byte-for-byte golden comparison."""
    if len(data) < 8 or data[:3] != b"MND":
        raise ValueError("expected MND header")
    text = f"\nHeader : MND version {data[3]}\nTarget unit {int.from_bytes(data[4:8], 'little')}\n"
    offset, line = 8, 0
    while offset < len(data):
        row = decode(data, offset)
        if row["tag"] in (0x86, 0x88):
            line = row["line"]
        if row["kind"] == "line_delta":
            line += row["delta"]
            delta = {0x80: "", 0x82: f" by byte {row['delta']}", 0x84: f" by word {row['delta']}"}[row["tag"]]
            rendered = f"Inc SLD linenum{delta} (to {line})"
        else:
            rendered = body(row)
        text += f"{offset:06x}: ${row['address']:08x} {row['tag']:x} {rendered}\n"
        offset = row["end"]
    return text
