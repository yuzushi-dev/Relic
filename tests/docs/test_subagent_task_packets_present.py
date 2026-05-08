"""PR13 — local handoff docs include every dispatchable task packet."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKET_DIR = ROOT / "dev_docs" / "orchestration" / "SUBAGENT_TASK_PACKETS"
DISPATCHABLE_IDS = [
    "PR00", "PR01", "PR02", "PR03", "PR04", "PR05", "PR06", "PR07", "PR08", "PR09",
    "PR10", "PR11", "PR12", "PR13", "PR14", "PR15",
    "PR16A", "PR16B", "PR16C", "PR16D", "PR16E",
    "PR19A", "PR19B", "PR19C", "PR19D", "PR19E", "PR19F",
    "PR20A", "PR20B", "PR20C", "PR20D", "PR20E", "PR20F", "PR20G",
    "PR22A", "PR22B", "PR22C", "PR22D", "PR22E", "PR22F",
    "PR22G", "PR22H", "PR22I", "PR22J",
]


def test_packets_present() -> None:
    if not PACKET_DIR.exists():
        pytest.skip("dev_docs is intentionally gitignored and absent in publishable clones")
    missing = [
        tid for tid in DISPATCHABLE_IDS
        if not (PACKET_DIR / f"{tid}.md").exists()
    ]
    assert not missing, f"missing packets: {missing}"
