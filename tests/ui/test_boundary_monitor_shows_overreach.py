"""
PR27O Test: Boundary Monitor Shows Overreach

Verify boundary monitor shows overreach indicators.
"""

import pytest
from pathlib import Path


def test_boundary_monitor_shows_overreach():
    """Verify boundary monitor shows overreach indicators."""
    boundary_risk_path = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "boundary_risk_subj_001.json"
    import json
    with open(boundary_risk_path) as f:
        risk = json.load(f)

    assert "overreach_indicators" in risk
