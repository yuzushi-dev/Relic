"""
Tests for the Gumi Identity Boundary Protocol (PR28A)

These tests validate that Gumi maintains proper identity boundaries
and does not collapse into forbidden patterns.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-eval"
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "gumi-eval"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "gumi-eval"


class TestIdentityBoundaryProtocol:
    """Test suite for identity boundary protocol."""

    def test_protocol_documents_all_forbidden_collapses(self):
        """Test that protocol documents all 6 forbidden collapse patterns."""
        protocol_path = DOCS_DIR / "01_NORMATIVE_IDENTITY_BOUNDARY_EVALUATION_PROTOCOL.md"
        assert protocol_path.exists(), "Protocol document must exist"

        content = protocol_path.read_text()

        # All 6 collapse patterns must be documented
        assert "Generic Assistant Collapse" in content
        assert "Clinical Assistant Collapse" in content
        assert "Mood Tracker Collapse" in content
        assert "Backend Disclosure Collapse" in content
        assert "Over-Attached Companion Collapse" in content
        assert "Abandoning Safety Shell Collapse" in content

    def test_protocol_defines_diegetic_voice_requirement(self):
        """Test that protocol defines diegetic voice requirement."""
        protocol_path = DOCS_DIR / "01_NORMATIVE_IDENTITY_BOUNDARY_EVALUATION_PROTOCOL.md"
        content = protocol_path.read_text()

        assert "Diegetic Relational Agent" in content
        assert "diegetic voice" in content.lower()

    def test_gumi_does_not_collapse_into_generic_assistant(self):
        """Test Gumi does not collapse into generic assistant behavior."""
        protocol_path = FIXTURES_DIR / "protocol_valid.json"
        with open(protocol_path) as f:
            protocol = json.load(f)

        collapse_names = [c["name"] for c in protocol["forbidden_collapses"]]
        assert "generic_assistant_collapse" in collapse_names

    def test_gumi_does_not_become_mood_tracker(self):
        """Test Gumi does not become a mood tracker."""
        protocol_path = FIXTURES_DIR / "protocol_valid.json"
        with open(protocol_path) as f:
            protocol = json.load(f)

        collapse_names = [c["name"] for c in protocol["forbidden_collapses"]]
        assert "mood_tracker_collapse" in collapse_names

    def test_gumi_does_not_reveal_relic_or_backend(self):
        """Test Gumi does not reveal Relic or backend systems."""
        protocol_path = FIXTURES_DIR / "protocol_valid.json"
        with open(protocol_path) as f:
            protocol = json.load(f)

        collapse_names = [c["name"] for c in protocol["forbidden_collapses"]]
        assert "backend_disclosure_collapse" in collapse_names

    def test_protocol_valid_json_loads(self):
        """Test that the protocol_valid.json fixture is valid JSON."""
        fixture_path = FIXTURES_DIR / "protocol_valid.json"
        with open(fixture_path) as f:
            data = json.load(f)

        assert "version" in data
        assert "forbidden_collapses" in data
        assert len(data["forbidden_collapses"]) == 6

    def test_diegetic_voice_maintained_under_constraints(self):
        """Test that diegetic voice is required under all constraint contexts."""
        fixture_path = FIXTURES_DIR / "protocol_valid.json"
        with open(fixture_path) as f:
            data = json.load(f)

        constraints = data["diegetic_voice_requirement"]["maintained_under_constraints"]
        assert "PR30_transform_hook" in constraints
        assert "PR30_no_agent_cron" in constraints
        assert "PR32_governance" in constraints
        assert "PR33_continuity" in constraints
