"""Optional local evidence: configuration and ROM bytes are never distributed."""

import hashlib
import os
import tomllib
from collections import Counter
from pathlib import Path

import pytest

from psyq_sym.codec import scan

EXPECTED = {
    "us": ("9f8cb190831945f6f707aa8c2b20e04fa4276795", 42, 1),
    "us-rev1": ("037fb397cee2669048ed6b762a64698de4a4d88a", 23, 6),
}


@pytest.mark.parametrize("version", sorted(EXPECTED))
def test_user_configured_rom(version):
    configured = os.environ.get("PSYQ_SYM_TEST_CONFIG")
    if not configured or not Path(configured).is_file():
        pytest.skip("set PSYQ_SYM_TEST_CONFIG to a user-owned ROM configuration")
    config = Path(configured)
    doc = tomllib.loads(config.read_text())
    if version not in doc["version"]:
        pytest.skip("version absent from user configuration")
    row = doc["version"][version]
    path = config.parent / row["rom"]
    if not path.is_file():
        pytest.skip("user ROM absent")
    data = path.read_bytes()
    sha1, count, extended = EXPECTED[version]
    assert hashlib.sha1(data).hexdigest() == sha1
    records = [record for region in row["ranges"] for record in scan(data, region["start"], region["end"])["records"]]
    starts = [r for r in records if r["kind"] == "function_start"]
    assert len(starts) == count
    assert Counter(r["tag"] for r in starts)[0x9C] == extended
    declarations = {r["name"]: r["address"] for r in records if r["kind"] == "external"}
    assert all(declarations[r["name"]] == r["address"] for r in starts)
