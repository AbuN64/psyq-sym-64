"""Read explicit project-owned ranges, or locate candidate fragments in a ROM."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from psyq_sym.catalog import names
from psyq_sym.codec import DecodeError, scan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--locate", action="store_true", help="scan the entire ROM; report candidate runs and gaps")
    parser.add_argument("--records", action="store_true", help="emit raw decoded catalog rather than generic names")
    args = parser.parse_args()
    try:
        doc = tomllib.loads(args.config.read_text())
        row = doc["version"][args.version]
        data = (args.config.parent / row["rom"]).read_bytes()
        ranges = [{"start": 0, "end": len(data)}] if args.locate else row["ranges"]
        merged = {"records": [], "types": [], "runs": [], "gaps": []}
        for region in ranges:
            decoded = scan(data, region["start"], region["end"])
            for key in merged:
                merged[key].extend(decoded[key])
        result = (
            merged
            if args.records or args.locate
            else names(
                merged,
                args.version,
                row["address_mask"],
                doc["abi"]["pointer_size"],
                doc["abi"]["int_size"],
                doc["abi"]["long_size"],
            )
        )
        json.dump(result, sys.stdout, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    except (OSError, ValueError, KeyError, DecodeError) as error:
        sys.stderr.write(f"psyq-sym: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
