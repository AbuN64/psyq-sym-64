"""Lossless generic names/types with explicit ABI and provenance."""

from __future__ import annotations

from typing import Any


def names(
    catalog: dict[str, Any], version: str, address_mask: int, pointer_size: int, int_size: int, long_size: int
) -> dict[str, Any]:
    """Normalize names without assuming a console address map or host C ABI."""
    base_sizes = {
        "char": 1,
        "unsigned char": 1,
        "short": 2,
        "unsigned short": 2,
        "int": int_size,
        "unsigned int": int_size,
        "long": long_size,
        "unsigned long": long_size,
        "float": 4,
        "double": 8,
        "enum": int_size,
        "enum_member": int_size,
    }

    def size(row: dict[str, Any]) -> int | None:
        if row["kind"] == "bitfield":
            return None  # record_size is the bit width, not a byte count
        typ = row["type"]
        modifiers = typ["modifiers"]
        if modifiers and modifiers[0] == "pointer":
            return pointer_size
        if modifiers and modifiers[0] == "function":
            return None
        if modifiers and modifiers[0] == "array":
            return row["size"] or None
        return base_sizes.get(typ["base"], row["size"] or None)

    records = catalog["records"]
    functions = []
    active = None
    for row in records:
        if row["kind"] == "function_start":
            active = {**row, "address": row["address"] | address_mask, "version": version, "parameters": []}
            functions.append(active)
        elif row["kind"] == "function_end":
            active = None
        elif active and row["kind"] in ("argument", "register_argument"):
            active["parameters"].append(row)
    structs, enums = [], []
    for row in catalog["types"]:
        dest = enums if row["kind"] == "enum_tag" else structs
        dest.append(
            {
                **row,
                "version": version,
                "members": [
                    {
                        **m,
                        **(
                            {"value": m["address"] if m["address"] < 0x80000000 else m["address"] - 0x100000000}
                            if m["kind"] == "enum_member"
                            else {"offset": m["address"]}
                        ),
                        "size": size(m),
                        "record_size": m["size"],
                        **(
                            {}
                            if m["kind"] == "enum_member"
                            else {"offset_unit": "bits" if m["kind"] == "bitfield" else "bytes"}
                        ),
                    }
                    for m in row["members"]
                ],
            }
        )
    return {
        "schema": 1,
        "functions": functions,
        "structs": structs,
        "enums": enums,
        "typedefs": [{**r, "version": version, "storage_size": size(r)} for r in records if r["kind"] == "typedef"],
    }
