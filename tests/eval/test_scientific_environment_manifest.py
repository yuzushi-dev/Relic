"""Scientific reproducibility environment manifest contracts."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import eval_run
import relic.eval.scientific_environment_manifest as environment_manifest
from relic.eval.scientific_environment_manifest import (
    build_scientific_environment_manifest,
)


def test_scientific_environment_manifest_records_reproducibility_inputs():
    manifest = build_scientific_environment_manifest()

    assert manifest["report_id"] == "scientific_environment_manifest_v1"
    assert manifest["claim_scope"] == "reproducible_environment_provenance"
    assert manifest["validation"]["valid"] is True

    summary = manifest["summary"]
    assert summary["dependency_lockfile_present"] is True
    assert summary["full_repo_container_present"] is True
    assert isinstance(summary["working_tree_clean"], bool)
    assert summary["required_verification_command_count"] >= 5
    if summary["dirty_file_count"] > 0:
        assert summary["release_artifact_ready"] is False

    git = manifest["git"]
    assert git["current_commit"]
    assert git["branch"]
    assert isinstance(git["dirty_file_count"], int)

    environment = manifest["environment"]
    assert environment["python_version"]
    assert environment["python_implementation"]
    assert environment["platform"]

    dependency_paths = {entry["path"] for entry in manifest["dependency_files"]}
    assert "pyproject.toml" in dependency_paths
    assert "uv.lock" in dependency_paths
    for entry in manifest["dependency_files"]:
        assert entry["sha256"].startswith("sha256:")
        assert entry["size_bytes"] > 0

    container_paths = {entry["path"] for entry in manifest["container_files"]}
    assert "Dockerfile" in container_paths
    assert ".dockerignore" in container_paths

    # Exclusions mirror the --ignore entries of pyproject addopts, whatever they are now.
    ignored_paths = {entry["path"] for entry in manifest["excluded_tests"]}
    assert ignored_paths == set(
        environment_manifest._ignored_paths_from_addopts(
            manifest["pytest_configuration"]["addopts"]
        )
    )
    assert summary["excluded_test_count"] == len(manifest["excluded_tests"])
    assert all(entry["reason"] for entry in manifest["excluded_tests"])

    commands = {entry["id"]: entry["command"] for entry in manifest["required_verification_commands"]}
    assert "scientific_claim_readiness_workflow" in commands
    assert "scientific_defensibility_gate" in commands
    assert "scientific_reproducibility_snapshot" in commands
    assert "docker_build_scientific_environment" in commands
    assert "broad_pytest_scientific_surface" in commands
    assert "--experiment scientific_environment_manifest" in commands["environment_manifest"]
    assert "scripts/scientific_claim_readiness.py --mode full" in commands["scientific_claim_readiness_workflow"]
    assert "docker build" in commands["docker_build_scientific_environment"]


def test_eval_run_scientific_environment_manifest_outputs_json(tmp_path, capsys):
    output_path = tmp_path / "scientific-environment-manifest.json"

    exit_code = eval_run.main(
        [
            "--experiment",
            "scientific_environment_manifest",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    assert exit_code == 0
    stdout = json.loads(capsys.readouterr().out)
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout["report_id"] == "scientific_environment_manifest_v1"
    assert output["summary"] == stdout["summary"]


def test_ignored_paths_are_parsed_from_addopts():
    parse = environment_manifest._ignored_paths_from_addopts
    assert parse("-v --ignore=tests/a.py --ignore tests/b.py -m 'not slow'") == [
        "tests/a.py",
        "tests/b.py",
    ]
    assert parse("-v -m 'not slow'") == []


def test_manifest_without_pytest_exclusions_is_valid(monkeypatch):
    monkeypatch.setattr(
        environment_manifest,
        "_pytest_configuration",
        lambda pyproject: {"testpaths": [], "addopts": "-v", "markers": [], "ignored_paths": []},
    )

    manifest = build_scientific_environment_manifest()

    assert manifest["excluded_tests"] == []
    assert manifest["summary"]["excluded_test_count"] == 0
    assert manifest["validation"]["valid"] is True


def test_undocumented_exclusion_still_gets_a_reason(monkeypatch):
    monkeypatch.setattr(
        environment_manifest,
        "_pytest_configuration",
        lambda pyproject: {
            "testpaths": [],
            "addopts": "",
            "markers": [],
            "ignored_paths": ["tests/new_exclusion.py"],
        },
    )

    manifest = build_scientific_environment_manifest()

    assert manifest["excluded_tests"][0]["path"] == "tests/new_exclusion.py"
    assert manifest["excluded_tests"][0]["reason"]
    assert manifest["validation"]["valid"] is True


def test_git_state_falls_back_to_container_source_metadata(monkeypatch):
    monkeypatch.setattr(environment_manifest, "_git", lambda args: "")
    monkeypatch.setenv("RELIC_SOURCE_COMMIT", "abc123")
    monkeypatch.setenv("RELIC_SOURCE_BRANCH", "container-branch")

    git = environment_manifest._git_state()

    assert git["current_commit"] == "abc123"
    assert git["branch"] == "container-branch"


def test_root_dockerfile_copies_container_manifest_inputs():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert any(
        line.startswith("COPY ")
        and "Dockerfile" in line
        and ".dockerignore" in line
        for line in dockerfile.splitlines()
    )
