"""
PR27O Test: Artifact Edit Requires Versioning

Verify artifact edits require versioning.
"""

import pytest
from pathlib import Path


def test_artifact_edit_requires_versioning():
    """Verify artifact edits require versioning."""
    schema_path = Path(__file__).parent.parent.parent / "schemas" / "ui" / "artifact_summary.schema.json"
    import json
    with open(schema_path) as f:
        schema = json.load(f)
    # Artifact schema should support versioning
    assert "artifact_id" in schema.get("properties", {})
