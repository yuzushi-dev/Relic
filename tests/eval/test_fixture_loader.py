"""Tests for eval fixtures module."""

import json

import pytest

from relic.eval.fixtures import (
    EvalScenario,
    FixtureLoader,
    FixtureType,
    ScenarioType,
)


class TestEvalScenario:
    """Tests for EvalScenario dataclass."""

    def test_scenario_creation(self):
        """Test creating an evaluation scenario."""
        scenario = EvalScenario(
            scenario_id="test_1",
            scenario_type=ScenarioType.MP1,
            fixture_type=FixtureType.MEMORY_POSITIVE,
            prompt="Test prompt",
            expected_response="Test response",
        )

        assert scenario.scenario_id == "test_1"
        assert scenario.scenario_type == ScenarioType.MP1
        assert scenario.fixture_type == FixtureType.MEMORY_POSITIVE

    def test_scenario_to_dict(self):
        """Test serializing scenario to dict."""
        scenario = EvalScenario(
            scenario_id="test_1",
            scenario_type=ScenarioType.MP1,
            fixture_type=FixtureType.MEMORY_POSITIVE,
            prompt="Test prompt",
            expected_response="Test response",
        )

        data = scenario.to_dict()
        assert data["scenario_id"] == "test_1"
        assert data["scenario_type"] == "mp1"

    def test_scenario_from_dict(self):
        """Test deserializing scenario from dict."""
        data = {
            "scenario_id": "test_1",
            "scenario_type": "mp1",
            "fixture_type": "memory_positive",
            "prompt": "Test prompt",
            "expected_response": "Test response",
            "metadata": {},
        }

        scenario = EvalScenario.from_dict(data)
        assert scenario.scenario_id == "test_1"
        assert scenario.scenario_type == ScenarioType.MP1


class TestFixtureLoader:
    """Tests for FixtureLoader."""

    def test_loader_initialization(self):
        """Test FixtureLoader initialization with default path."""
        loader = FixtureLoader()
        assert loader.fixtures_dir.exists()

    def test_loader_with_custom_path(self, tmp_path):
        """Test FixtureLoader with custom fixtures directory."""
        loader = FixtureLoader(fixtures_dir=tmp_path)
        assert loader.fixtures_dir == tmp_path

    def test_load_jsonl_file_not_found(self):
        """Test loading non-existent fixture file."""
        loader = FixtureLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_jsonl("nonexistent/fixture.jsonl")

    def test_load_jsonl_valid_file(self, tmp_path):
        """Test loading a valid JSONL fixture file."""
        # Create test fixture
        fixture_path = tmp_path / "test_fixture.jsonl"
        scenarios = [
            {
                "scenario_id": "test_1",
                "scenario_type": "mp1",
                "fixture_type": "memory_positive",
                "prompt": "Test prompt 1",
                "expected_response": "Test response 1",
            },
            {
                "scenario_id": "test_2",
                "scenario_type": "mp2",
                "fixture_type": "memory_positive",
                "prompt": "Test prompt 2",
                "expected_response": "Test response 2",
            },
        ]

        with open(fixture_path, "w") as f:
            for scenario in scenarios:
                f.write(json.dumps(scenario) + "\n")

        # Load and verify
        loader = FixtureLoader(fixtures_dir=tmp_path)
        loaded = loader.load_jsonl("test_fixture.jsonl")

        assert len(loaded) == 2
        assert loaded[0].scenario_id == "test_1"
        assert loaded[1].scenario_id == "test_2"

    def test_list_fixtures(self):
        """Test listing available fixtures."""
        loader = FixtureLoader()
        fixtures = loader.list_fixtures()
        assert isinstance(fixtures, list)
