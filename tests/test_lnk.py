from pathlib import Path

import pytest

from psyq_sym.lnk import LnkError, decode, expression, locate

FIX = Path(__file__).parent / "fixtures"


def test_patch_expression_adds_section_base_and_constant():
    value, end = expression(bytes.fromhex("2c040300" "0004000000"), 0)
    assert value == ("add", ("secbase", 3), ("const", 4))
    assert end == 9


def test_unknown_expression_opcode_is_refused():
    with pytest.raises(LnkError):
        expression(b"\x7f", 0)


def test_real_portal_slice_decodes_patches_lines_switch_and_code_to_its_end():
    raw = (FIX / "lnk_portal_slice.bin").read_bytes()
    records, stop = decode(raw)
    kinds = [r.kind for r in records]
    assert stop == 462  # the slice ends inside the next patch, which is not decoded
    assert kinds[0] == "patch"
    assert kinds.count("switch") == 1
    code = next(r for r in records if r.kind == "code" and len(r.args[0]) == 125)
    assert code.args[0] == bytes(125)
    patch = next(r for r in records if r.kind == "patch")
    assert patch.args == (0x60, 0x3A, ("add", ("secbase", 1), ("const", 0)))


def test_locate_skips_a_partial_leading_record():
    raw = (FIX / "lnk_portal_slice.bin").read_bytes()
    start, records, _ = locate(b"\xff\xff\xff" + raw, 16)
    assert start == 3
    assert records[0].kind == "patch"
