from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "datasets" / "regression" / "golden_v1"
GATE_PATH = ROOT / "hooks" / "shared" / "artifact-gate.ts"


def test_golden_v1_required_files_exist() -> None:
    required = [
        GOLDEN / "messages.jsonl",
        GOLDEN / "sessions" / "openclaw" / "session-001.jsonl",
        GOLDEN / "sessions" / "hermes" / "sessions.json",
        GOLDEN / "sessions" / "hermes" / "session-001.jsonl",
        GOLDEN / "run_manifest.expected.json",
        GOLDEN / "observations.expected.jsonl",
        GOLDEN / "traits.expected.json",
        GOLDEN / "hypotheses.expected.json",
        GOLDEN / "PORTRAIT.expected.md",
        GOLDEN / "artifact_gate.expected.json",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"golden_v1 missing required files: {missing}"


def test_manifest_defines_comparison_rules_explicitly() -> None:
    manifest = json.loads((GOLDEN / "run_manifest.expected.json").read_text(encoding="utf-8"))

    assert manifest["golden_version"] == "v1"
    match_rule = manifest["observation_match_rule"]
    assert match_rule["identity_fields"] == ["facet_id", "source_ref"]
    assert "equivalent_if" in match_rule and match_rule["equivalent_if"]
    assert manifest["bit_exact_layers"] == ["observations", "traits", "artifact_gate"]
    tolerance_layers = manifest["tolerance_layers"]
    assert set(tolerance_layers) == {"portrait", "hypotheses"}
    for spec in tolerance_layers.values():
        assert spec["owner"]
        assert spec["rule"]


def test_expected_observation_identities_are_unique() -> None:
    seen: set[tuple[str, str]] = set()
    observations_path = GOLDEN / "observations.expected.jsonl"
    for line in observations_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        identity = (row["facet_id"], row["source_ref"])
        assert identity not in seen, f"duplicate observation identity: {identity!r}"
        seen.add(identity)


def test_artifact_gate_expectation_matches_runtime_gate() -> None:
    expected = json.loads((GOLDEN / "artifact_gate.expected.json").read_text(encoding="utf-8"))
    gate_src = GATE_PATH.read_text(encoding="utf-8")
    match = re.search(r"INJECTABLE_ARTIFACTS\s*(?::[^=]+)?=\s*\[([^\]]+)\]", gate_src)
    assert match, "Could not locate INJECTABLE_ARTIFACTS array literal"
    whitelist = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))

    for allowed in expected["injectable_artifacts"]:
        assert allowed in whitelist
    for forbidden in expected["forbidden_artifacts"]:
        assert forbidden not in whitelist
