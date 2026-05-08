"""
PR27O Test: Careful Distancing Control Available

Verify careful distancing control is available.
"""

import pytest
from pathlib import Path


def test_careful_distancing_control_available():
    """Verify careful distancing control is available."""
    boundary_risk_path = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "boundary_risk_subj_001.json"
    import json
    with open(boundary_risk_path) as f:
        risk = json.load(f)

    assert "careful_distancing_enabled" in risk
