"""PR15, replication/ root must hold required schemas and example bundle."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_replication_dir_present() -> None:
    assert (ROOT / "replication" / "README.md").exists()


def test_replication_schemas_present() -> None:
    for s in (
        "run_manifest.schema.json",
        "artifact_checksums.schema.json",
        "debug_bundle.schema.json",
        "privacy_exclusion_report.schema.json",
    ):
        assert (ROOT / "replication" / s).exists(), s


def test_example_bundle_present() -> None:
    assert (ROOT / "replication" / "example_bundle").is_dir()
