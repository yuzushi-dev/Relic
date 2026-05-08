"""Validates each S01-S12 scenario fixture against the gumi_scenario schema."""

import json
import pathlib
from typing import Dict, Any

import pytest

SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schemas" / "gumi-identity-attractor" / "gumi_scenario.schema.json"
SCENARIOS_DIR = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "gumi-identity-attractor" / "scenarios"

SCENARIO_IDS = [f"S{i:02d}" for i in range(1, 13)]


@pytest.fixture
def schema() -> Dict[str, Any]:
    with open(SCHEMA_PATH, "r") as f:
        return json.load(f)


def jsonschema_validate(data: Dict[str, Any], schema: Dict[str, Any]) -> list:
    """Simple jsonschema validator (draft 2020-12). Returns list of error messages."""
    errors = []

    # Check required fields
    for required_field in schema.get("required", []):
        if required_field not in data:
            errors.append(f"Missing required field: {required_field}")

    # Check field types
    properties = schema.get("properties", {})
    for field_name, field_schema in properties.items():
        if field_name not in data:
            continue
        field_value = data[field_name]
        expected_type = field_schema.get("type")
        if expected_type == "object" and not isinstance(field_value, dict):
            errors.append(f"Field '{field_name}' must be object, got {type(field_value).__name__}")
        elif expected_type == "array" and not isinstance(field_value, list):
            errors.append(f"Field '{field_name}' must be array, got {type(field_value).__name__}")
        elif expected_type == "string" and not isinstance(field_value, str):
            errors.append(f"Field '{field_name}' must be string, got {type(field_value).__name__}")
        # Check array items
        if expected_type == "array" and isinstance(field_value, list):
            items_schema = field_schema.get("items", {})
            items_type = items_schema.get("type")
            if items_type:
                for i, item in enumerate(field_value):
                    if not isinstance(item, str):
                        errors.append(f"Field '{field_name}[{i}]' must be string, got {type(item).__name__}")

    # Check additionalProperties
    if not schema.get("additionalProperties", True):
        extra_fields = set(data.keys()) - set(properties.keys())
        if extra_fields:
            errors.append(f"Unexpected fields: {extra_fields}")

    return errors


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_validates_against_schema(schema, scenario_id):
    """Each S01-S12 fixture must be valid against the gumi_scenario schema."""
    scenario_path = SCENARIOS_DIR / f"{scenario_id}_*.json"
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    assert len(matching) == 1, f"Expected exactly one fixture for {scenario_id}, found: {matching}"
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        scenario_data = json.load(f)

    errors = jsonschema_validate(scenario_data, schema)
    assert not errors, f"Schema validation failed for {scenario_id}: {errors}"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_has_all_required_fields(schema, scenario_id):
    """Each scenario must have all required top-level fields."""
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        data = json.load(f)

    required = schema.get("required", [])
    missing = [f for f in required if f not in data]
    assert not missing, f"{scenario_id} missing required fields: {missing}"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_hard_fails_is_list_of_strings(scenario_id):
    """hard_fails must be a non-empty list of strings."""
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        data = json.load(f)

    hard_fails = data.get("hard_fails", [])
    assert isinstance(hard_fails, list), f"{scenario_id}: hard_fails must be a list"
    assert len(hard_fails) > 0, f"{scenario_id}: hard_fails must not be empty"
    for item in hard_fails:
        assert isinstance(item, str), f"{scenario_id}: hard_fails items must be strings, got {type(item).__name__}"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_expected_behavior_is_list_of_strings(scenario_id):
    """expected_behavior must be a non-empty list of strings."""
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        data = json.load(f)

    expected = data.get("expected_behavior", [])
    assert isinstance(expected, list), f"{scenario_id}: expected_behavior must be a list"
    assert len(expected) > 0, f"{scenario_id}: expected_behavior must not be empty"
    for item in expected:
        assert isinstance(item, str), f"{scenario_id}: expected_behavior items must be strings"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_scoring_dimensions_is_non_empty_list(scenario_id):
    """scoring_dimensions must be a non-empty list of strings."""
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        data = json.load(f)

    dims = data.get("scoring_dimensions", [])
    assert isinstance(dims, list), f"{scenario_id}: scoring_dimensions must be a list"
    assert len(dims) > 0, f"{scenario_id}: scoring_dimensions must not be empty"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_id_matches_filename(scenario_id):
    """scenario_id field must match the numeric prefix in the filename."""
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    assert len(matching) == 1, f"No unique match for {scenario_id}"
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        data = json.load(f)

    assert data.get("scenario_id") == scenario_id, \
        f"scenario_id field '{data.get('scenario_id')}' does not match filename prefix '{scenario_id}'"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_runtime_context_is_object(scenario_id):
    """runtime_context must be an object (dict)."""
    matching = list(SCENARIOS_DIR.glob(f"{scenario_id}_*.json"))
    scenario_file = matching[0]

    with open(scenario_file, "r") as f:
        data = json.load(f)

    rc = data.get("runtime_context")
    assert isinstance(rc, dict), f"{scenario_id}: runtime_context must be a dict, got {type(rc).__name__}"