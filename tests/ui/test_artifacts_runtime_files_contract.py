"""
PR27K — Artifacts and Runtime Files contract tests.

Verifies that the artifact fixture satisfies the schema and all acceptance criteria:
- Every artifact is subject-scoped.
- Runtime files cannot be silently edited (versioning enforced).
- Artifact status is visible.
- Artifact versions can be compared (version field present).
- Cross-subject artifact copy is blocked (subject_id uniqueness per fixture).

Block conditions tested:
- BLOCKED_ARTIFACT_WITHOUT_SUBJECT
- BLOCKED_UNVERSIONED_ARTIFACT_EDIT
- BLOCKED_CROSS_SUBJECT_ARTIFACT_COPY
"""

import json
import pytest
from pathlib import Path

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "researcher-workbench" / "artifacts_subj_001.json"
SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "ui" / "artifact_summary.schema.json"

REQUIRED_ARTIFACT_FIELDS = {
    "artifact_id",
    "subject_id",
    "gumi_instance_id",
    "artifact_type",
    "path",
    "hash",
    "schema_version",
    "source_snapshot",
    "status",
    "generated_at",
    "used_by_runtime",
}

VALID_STATUSES = {"active", "stale", "quarantined", "superseded"}

VALID_ARTIFACT_TYPES = {
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "PORTRAIT.md",
    "subject_profile.json",
    "gumi_profile.json",
    "gumi_world_state.json",
    "runtime_profile_pack",
    "cron_manifest",
    "policy_snapshot",
    "artifact_registry",
}


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    with open(FIXTURE_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def artifacts(fixture_data):
    return fixture_data["artifacts"]


# --- Schema presence ---

def test_fixture_has_subject_id(fixture_data):
    assert "subject_id" in fixture_data
    assert fixture_data["subject_id"].startswith("SUBJ-")


def test_fixture_has_gumi_instance_id(fixture_data):
    assert "gumi_instance_id" in fixture_data
    assert fixture_data["gumi_instance_id"].startswith("GUMI-")


def test_fixture_has_artifacts_list(fixture_data):
    assert "artifacts" in fixture_data
    assert isinstance(fixture_data["artifacts"], list)
    assert len(fixture_data["artifacts"]) > 0


# --- Per-artifact required fields ---

def test_all_artifacts_have_required_fields(artifacts):
    for artifact in artifacts:
        missing = REQUIRED_ARTIFACT_FIELDS - set(artifact.keys())
        assert not missing, f"Artifact {artifact.get('artifact_id')} missing fields: {missing}"


# --- Acceptance criteria: every artifact is subject-scoped ---

def test_every_artifact_has_subject_id(artifacts):
    """BLOCKED_ARTIFACT_WITHOUT_SUBJECT: subject_id must be present and non-null."""
    for artifact in artifacts:
        assert "subject_id" in artifact, f"Artifact {artifact.get('artifact_id')} has no subject_id"
        assert artifact["subject_id"], f"Artifact {artifact.get('artifact_id')} has empty subject_id"
        assert artifact["subject_id"].startswith(("subj_", "SUBJ-")), \
            f"Artifact {artifact.get('artifact_id')} subject_id must start with subj_ or SUBJ-"


def test_all_artifacts_belong_to_fixture_subject(fixture_data, artifacts):
    """All artifacts in this fixture must belong to the declared subject."""
    declared_subject = fixture_data["subject_id"]
    for artifact in artifacts:
        assert artifact["subject_id"] == declared_subject, \
            f"Artifact {artifact['artifact_id']} subject_id {artifact['subject_id']} != {declared_subject}"


# --- Acceptance criteria: artifact status visible ---

def test_every_artifact_has_valid_status(artifacts):
    for artifact in artifacts:
        assert artifact["status"] in VALID_STATUSES, \
            f"Artifact {artifact['artifact_id']} has invalid status: {artifact['status']}"


# --- Acceptance criteria: runtime files cannot be silently edited (versioning) ---

def test_every_artifact_has_version(artifacts):
    """BLOCKED_UNVERSIONED_ARTIFACT_EDIT: version field must be present."""
    for artifact in artifacts:
        assert "version" in artifact, \
            f"Artifact {artifact['artifact_id']} missing 'version' field — edit tracking not possible"
        assert isinstance(artifact["version"], int), \
            f"Artifact {artifact['artifact_id']} version must be integer"
        assert artifact["version"] >= 1, \
            f"Artifact {artifact['artifact_id']} version must be >= 1"


def test_every_artifact_has_hash(artifacts):
    """Content hash must be present for integrity verification."""
    for artifact in artifacts:
        assert artifact["hash"].startswith("sha256:"), \
            f"Artifact {artifact['artifact_id']} hash must start with 'sha256:'"


# --- Acceptance criteria: artifact versions can be compared ---

def test_non_v1_artifacts_reference_previous_version(artifacts):
    """Artifacts at version > 1 must have previous_version_id for comparison chain."""
    for artifact in artifacts:
        version = artifact.get("version", 1)
        if version > 1:
            prev = artifact.get("previous_version_id")
            assert prev is not None and prev != "", \
                f"Artifact {artifact['artifact_id']} at version {version} must have previous_version_id"


def test_v1_artifacts_have_null_previous_version(artifacts):
    """First-version artifacts must have null previous_version_id."""
    for artifact in artifacts:
        if artifact.get("version", 1) == 1:
            prev = artifact.get("previous_version_id")
            assert prev is None, \
                f"Artifact {artifact['artifact_id']} at v1 should have null previous_version_id, got: {prev}"


# --- Acceptance criteria: cross-subject artifact copy blocked ---

def test_no_cross_subject_artifacts(artifacts):
    """BLOCKED_CROSS_SUBJECT_ARTIFACT_COPY: all artifacts must share the same subject_id."""
    subject_ids = {a["subject_id"] for a in artifacts}
    assert len(subject_ids) == 1, \
        f"Artifacts span multiple subjects — cross-subject copy detected: {subject_ids}"


# --- Artifact type validity ---

def test_all_artifact_types_are_valid(artifacts):
    for artifact in artifacts:
        assert artifact["artifact_type"] in VALID_ARTIFACT_TYPES, \
            f"Unknown artifact_type: {artifact['artifact_type']}"


# --- Quarantine fields ---

def test_quarantined_artifacts_have_reason(artifacts):
    for artifact in artifacts:
        if artifact["status"] == "quarantined":
            reason = artifact.get("quarantine_reason")
            assert reason, \
                f"Quarantined artifact {artifact['artifact_id']} must have quarantine_reason"


def test_non_quarantined_artifacts_have_null_or_absent_reason(artifacts):
    for artifact in artifacts:
        if artifact["status"] != "quarantined":
            reason = artifact.get("quarantine_reason")
            assert reason is None or reason == "", \
                f"Non-quarantined artifact {artifact['artifact_id']} should not have quarantine_reason"


# --- gumi_instance_id presence ---

def test_every_artifact_has_gumi_instance_id(artifacts):
    for artifact in artifacts:
        assert "gumi_instance_id" in artifact, \
            f"Artifact {artifact['artifact_id']} missing gumi_instance_id"
        assert artifact["gumi_instance_id"].startswith("GUMI-"), \
            f"Artifact {artifact['artifact_id']} gumi_instance_id must start with GUMI-"


# --- Coverage: all required artifact types present ---

def test_fixture_covers_all_required_artifact_types(artifacts):
    """Fixture must include all artifact types defined in the spec."""
    present_types = {a["artifact_type"] for a in artifacts}
    missing = VALID_ARTIFACT_TYPES - present_types
    assert not missing, f"Fixture missing artifact types: {missing}"
