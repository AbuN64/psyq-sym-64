"""Build invented Psy-Q records; no cartridge bytes or developer identifiers."""

import struct
from pathlib import Path


def string(value):
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def record(address, tag, payload=b""):
    return struct.pack("<IB", address, tag) + payload


def definition(address, storage, typ, size, name, *, dims=None, tag=""):
    payload = struct.pack("<HHI", storage, typ, size)
    kind = 0x94
    if dims is not None:
        kind = 0x96
        payload += struct.pack("<H", len(dims)) + b"".join(struct.pack("<I", n) for n in dims) + string(tag)
    return record(address, kind, payload + string(name))


def sample():
    rows = [
        definition(0, 10, 8, 16, "Example_t"),
        definition(0, 8, 6, 0, "x"),
        definition(4, 8, 6, 0, "y"),
        definition(8, 8, 0x18, 32, "next", dims=[], tag="Other_t"),
        definition(12, 18, 4, 3, "bits"),
        definition(16, 102, 0, 16, ".eos", dims=[], tag="Example_t"),
        definition(0, 13, 8, 16, "Example", dims=[], tag="Example_t"),
        definition(0, 15, 10, 4, "Mode"),
        definition(0, 16, 11, 0, "MODE_OFF"),
        definition(0xFFFFFFFF, 16, 11, 0, "MODE_UNKNOWN"),
        definition(4, 102, 0, 4, ".eos", dims=[], tag="Mode"),
        definition(0, 8, 0x78, 8, "links", dims=[2], tag="Example_t"),
        definition(0, 8, 0xF6, 24, "matrix", dims=[2, 3]),
        record(0x1000, 0x88, struct.pack("<I", 10) + string(r"C:\EXAMPLE\SOURCE\DEMO.C")),
        record(
            0x1000,
            0x8C,
            struct.pack("<HIHIiI", 29, 32, 31, 0x80010000, -4, 10)
            + string(r"C:\EXAMPLE\SOURCE\DEMO.C")
            + string("Example__Update"),
        ),
        record(0x1000, 0x90, struct.pack("<I", 10)),
        record(0x1004, 0x80),
        record(0x1008, 0x82, struct.pack("<B", 3)),
        record(0x100C, 0x84, struct.pack("<H", 260)),
        record(0x1010, 0x86, struct.pack("<I", 300)),
        record(0x1014, 0x92, struct.pack("<I", 301)),
        record(0x1018, 0x8E, struct.pack("<I", 302)),
        record(0, 0x8A),
    ]
    return b"MND\x01" + bytes(4) + b"".join(rows)


if __name__ == "__main__":
    Path(__file__).with_name("records.sym").write_bytes(sample())
