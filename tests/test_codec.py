from pathlib import Path

import pytest

from psyq_sym.catalog import names
from psyq_sym.codec import DecodeError, decode, scan
from psyq_sym.dump import dump

FIX = Path(__file__).parent / "fixtures"


def test_golden_exact_oracle_dump():
    assert dump((FIX / "records.sym").read_bytes()) == (FIX / "records.dump").read_text()


def test_extended_function_and_record_addresses_are_not_shifted():
    import struct

    def string(value):
        raw = value.encode("ascii")
        return bytes([len(raw)]) + raw

    raw = struct.pack("<IBHIHIiIiI", 0x1230, 0x9C, 29, 96, 31, 0x80010000, -4, 0x100000, -8, 55)
    raw += string(r"C:\EXAMPLE\SOURCE\DEMO.C") + string("Example__Rotate")
    row = decode(raw)
    assert row["name"] == "Example__Rotate" and row["address"] == 0x1230
    assert (row["frame_size"], row["float_register_mask"], row["float_mask_offset"]) == (96, 0x100000, -8)
    for end in range(1, len(raw)):
        with pytest.raises(DecodeError):
            decode(raw, 0, end)


def test_every_truncated_prefix_refuses_without_reading_outside_range():
    data = (FIX / "records.sym").read_bytes()
    pos = 8
    while pos < len(data):
        row = decode(data, pos)
        for end in range(pos + 1, row["end"]):
            with pytest.raises(DecodeError):
                decode(data, pos, end)
        pos = row["end"]


def test_gaps_isolated_matches_and_oversized_dimensions():
    data = (FIX / "records.sym").read_bytes()[8:]
    row = decode(data)
    isolated = data[: row["end"]]
    assert scan(isolated, 0, len(isolated))["records"] == []
    bad = bytes(4) + b"\x96\x08\x00\x08\x00" + bytes(4) + b"\xff\xff"
    with pytest.raises(DecodeError):
        decode(bad)
    wrapped = b"garbage!" + data + b"truncated"
    found = scan(wrapped, 0, len(wrapped))
    assert found["gaps"][0] == {"start": 0, "end": 8}
    assert found["gaps"][-1]["end"] == len(wrapped)


def test_pointer_size_not_referenced_struct_size():
    raw = (FIX / "records.sym").read_bytes()
    rows = scan(raw, 8, len(raw))["records"]
    row = next(r for r in rows if r.get("name") == "next")
    tag = {"kind": "struct_tag", "name": "Owner", "size": 4, "members": [row]}
    result = names({"records": [], "types": [tag]}, "v", 0, 4, 4, 4)
    member = result["structs"][0]["members"][0]
    assert member["record_size"] == 32
    assert member["size"] == 4


def test_enum_values_and_bit_widths_are_not_byte_offsets_or_sizes():
    enum = {
        "kind": "enum_member",
        "name": "NEGATIVE",
        "address": 0xFFFFFFFF,
        "size": 0,
        "type": {"base": "enum_member", "modifiers": [], "tag": "", "dimensions": []},
    }
    field = {
        "kind": "bitfield",
        "name": "bits",
        "address": 3,
        "size": 5,
        "type": {"base": "int", "modifiers": [], "tag": "", "dimensions": []},
    }
    result = names(
        {"records": [], "types": [{"kind": "enum_tag", "members": [enum]}, {"kind": "struct_tag", "members": [field]}]},
        "v",
        0,
        4,
        4,
        4,
    )
    member = result["enums"][0]["members"][0]
    assert member["value"] == -1 and member["size"] == 4 and "offset" not in member
    member = result["structs"][0]["members"][0]
    assert member["size"] is None and member["record_size"] == 5 and member["offset_unit"] == "bits"
