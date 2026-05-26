"""Reproducible environment manifest for scientific evaluation claims."""

from __future__ import annotations

import hashlib
import os
import platform
import shlex
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any


REPORT_ID = "scientific_environment_manifest_v1"
CLAIM_SCOPE = "reproducible_environment_provenance"
REVIEW_DATE = "2026-05-25"
REPO_ROOT = Path(__file__).resolve().parents[2]

DEPENDENCY_FILES = (
    "pyproject.toml",
    "uv.lock",
    "docs-requirements.txt",
)
CONTAINER_FILES = (
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "compose.yml",
    "ui/Dockerfile",
)
EXCLUDED_TEST_REASONS = {
    "tests/profile/test_bootstrap_tui_flow.py": (
        "explicitly ignored in pyproject pytest addopts; interactive/bootstrap "
        "profile flow requires a separate documented integration run"
    ),
    "tests/profile/test_gumi_hermes_cli.py": (
        "explicitly ignored in pyproject pytest addopts; CLI integration surface "
        "requires a separate documented integration run"
    ),
    "tests/profile/test_runtime_provisioning.py": (
        "explicitly ignored in pyproject pytest addopts; runtime provisioning "
        "requires environment-specific integration validation"
    ),
    "tests/bootstrap/test_pr28_bootstrap_outputs.py": (
        "explicitly ignored in pyproject pytest addopts; bootstrap output "
        "fixtures require a separate release-artifact check"
    ),
}
REQUIRED_VERIFICATION_COMMANDS = (
    {
        "id": "scientific_claim_readiness_workflow",
        "command": (
            "python scripts/scientific_claim_readiness.py --mode full "
            "--output-dir artifacts/scientific-claim-readiness --json"
        ),
        "purpose": "runs the single local workflow that generates reports, logs, verification outputs, and the claim-readiness gate result",
    },
    {
        "id": "environment_manifest",
        "command": (
            "python scripts/eval_run.py --experiment "
            "scientific_environment_manifest --output "
            "artifacts/scientific-environment-manifest.json --json"
        ),
        "purpose": "records commit, dependency lockfiles, pytest exclusions, and release readiness",
    },
    {
        "id": "scientific_reproducibility_snapshot",
        "command": (
            "python scripts/eval_run.py --experiment "
            "scientific_reproducibility_snapshot --output "
            "artifacts/scientific-reproducibility-snapshot.json --json"
        ),
        "purpose": "hashes locally reproducible scientific reports and expected outputs",
    },
    {
        "id": "scientific_defensibility_gate",
        "command": "python scripts/eval_run.py --experiment scientific_defensibility_gate --json",
        "purpose": "blocks broad scientific claims until external evidence requirements are met",
    },
    {
        "id": "docker_build_scientific_environment",
        "command": (
            "docker build --build-arg RELIC_SOURCE_COMMIT=$(git rev-parse HEAD) "
            "--build-arg RELIC_SOURCE_BRANCH=$(git rev-parse --abbrev-ref HEAD) "
            "-t relic-scientific-eval:local ."
        ),
        "purpose": "builds the root containerized evaluation environment from the locked repo context",
    },
    {
        "id": "broad_pytest_scientific_surface",
        "command": (
            "uv run --extra dev pytest --import-mode=importlib --cov=relic --cov=scripts "
            "--cov-report=json:artifacts/scientific-claim-readiness/scientific-surface-coverage.json "
            "--cov-report=term-missing:skip-covered tests/eval tests/gumi-eval "
            "tests/gumi_plugin tests/hermes_plugin tests/hermes_compat "
            "tests/test_db_schema.py -q"
        ),
        "purpose": "covers evaluation, Gumi, Hermes compatibility, and database schema surfaces and writes a coverage artifact",
    },
    {
        "id": "compileall",
        "command": "python -m compileall relic scripts tests/eval",
        "purpose": "checks Python syntax/import compilation for touched evaluation surfaces",
    },
    {
        "id": "privacy_marker_scan",
        "command": "python scripts/ci/check_no_raw_private_data.py",
        "purpose": "checks that raw/private data markers are not introduced into artifacts",
    },
    {
        "id": "diff_check",
        "command": "git diff --check",
        "purpose": "checks whitespace and patch hygiene before release packaging",
    },
)


def build_scientific_environment_manifest() -> dict[str, Any]:
    """Build a manifest describing the local environment needed to reproduce reports."""
    pyproject = _load_pyproject()
    pytest_config = _pytest_configuration(pyproject)
    dependency_files = _file_entries(DEPENDENCY_FILES)
    container_files = _file_entries(CONTAINER_FILES)
    git = _git_state()
    excluded_tests = _excluded_tests(pytest_config)

    dependency_lockfile_present = any(entry["path"] == "uv.lock" for entry in dependency_files)
    pyproject_present = any(entry["path"] == "pyproject.toml" for entry in dependency_files)
    working_tree_clean = git["dirty_file_count"] == 0
    full_repo_container_present = any(
        entry["path"] in {"Dockerfile", "docker-compose.yml", "compose.yml"}
        for entry in container_files
    )
    release_artifact_ready = (
        working_tree_clean
        and dependency_lockfile_present
        and pyproject_present
        and full_repo_container_present
    )

    validation_rules = [
        "git_revision_recorded",
        "dependency_lockfile_hashed",
        "pytest_exclusions_recorded",
        "required_verification_commands_recorded",
        "dirty_worktree_state_recorded",
        "container_environment_state_recorded",
    ]
    validation = {
        "valid": bool(
            git["current_commit"]
            and pyproject_present
            and dependency_lockfile_present
            and excluded_tests
            and REQUIRED_VERIFICATION_COMMANDS
        ),
        "checked_rules": validation_rules,
    }

    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "local_environment_provenance_manifest",
            "review_date": REVIEW_DATE,
            "provenance_basis": [
                "git_revision_and_dirty_state",
                "dependency_file_sha256",
                "pytest_configuration",
                "verification_command_inventory",
                "container_file_inventory",
            ],
        },
        "summary": {
            "dependency_lockfile_present": dependency_lockfile_present,
            "pyproject_present": pyproject_present,
            "working_tree_clean": working_tree_clean,
            "dirty_file_count": git["dirty_file_count"],
            "full_repo_container_present": full_repo_container_present,
            "release_artifact_ready": release_artifact_ready,
            "excluded_test_count": len(excluded_tests),
            "required_verification_command_count": len(REQUIRED_VERIFICATION_COMMANDS),
        },
        "git": git,
        "environment": _environment(pyproject),
        "dependency_files": dependency_files,
        "container_files": container_files,
        "package_metadata": _package_metadata(pyproject),
        "pytest_configuration": pytest_config,
        "excluded_tests": excluded_tests,
        "required_verification_commands": list(REQUIRED_VERIFICATION_COMMANDS),
        "validation": validation,
        "claim_limitations": _claim_limitations(
            working_tree_clean=working_tree_clean,
            full_repo_container_present=full_repo_container_present,
        ),
    }


def _load_pyproject() -> dict[str, Any]:
    path = REPO_ROOT / "pyproject.toml"
    if not path.exists():
        return {"parse_error": "pyproject.toml missing"}
    try:
        import tomllib
    except ModuleNotFoundError:
        return {"parse_error": "tomllib unavailable on this Python runtime"}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return {"parse_error": str(exc)}


def _file_entries(paths: tuple[str, ...]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative_path in paths:
        path = REPO_ROOT / relative_path
        if path.is_file():
            data = path.read_bytes()
            entries.append(
                {
                    "path": relative_path,
                    "sha256": f"sha256:{hashlib.sha256(data).hexdigest()}",
                    "size_bytes": len(data),
                }
            )
    return entries


def _git_state() -> dict[str, Any]:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"]) or os.environ.get(
        "RELIC_SOURCE_BRANCH", ""
    )
    commit = _git(["rev-parse", "HEAD"]) or os.environ.get("RELIC_SOURCE_COMMIT", "")
    status = _git(["status", "--porcelain=v1"])
    dirty_entries = _parse_dirty_status(status)
    return {
        "branch": branch,
        "current_commit": commit,
        "working_tree_clean": len(dirty_entries) == 0,
        "dirty_file_count": len(dirty_entries),
        "dirty_entries": dirty_entries,
    }


def _git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _parse_dirty_status(status: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in status.splitlines():
        if not line:
            continue
        entries.append(
            {
                "status": line[:2],
                "path": line[2:].lstrip(),
            }
        )
    return entries


def _environment(pyproject: dict[str, Any]) -> dict[str, str]:
    project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable": Path(sys.executable).name,
        "stdlib": sysconfig.get_path("stdlib") or "",
        "requires_python": str(project.get("requires-python", "")),
    }


def _package_metadata(pyproject: dict[str, Any]) -> dict[str, Any]:
    project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    if not isinstance(project, dict):
        project = {}
    optional_dependencies = project.get("optional-dependencies", {})
    if not isinstance(optional_dependencies, dict):
        optional_dependencies = {}
    return {
        "name": project.get("name", ""),
        "version": project.get("version", ""),
        "requires_python": project.get("requires-python", ""),
        "dependency_count": len(project.get("dependencies", []) or []),
        "optional_dependency_groups": sorted(optional_dependencies),
        "parse_error": pyproject.get("parse_error", ""),
    }


def _pytest_configuration(pyproject: dict[str, Any]) -> dict[str, Any]:
    pytest_options = (
        pyproject.get("tool", {})
        .get("pytest", {})
        .get("ini_options", {})
        if isinstance(pyproject, dict)
        else {}
    )
    if not isinstance(pytest_options, dict):
        pytest_options = {}
    addopts = str(pytest_options.get("addopts", ""))
    return {
        "testpaths": list(pytest_options.get("testpaths", []) or []),
        "addopts": addopts,
        "markers": list(pytest_options.get("markers", []) or []),
        "ignored_paths": _ignored_paths_from_addopts(addopts),
    }


def _ignored_paths_from_addopts(addopts: str) -> list[str]:
    ignored_paths: list[str] = []
    tokens = shlex.split(addopts)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--ignore="):
            ignored_paths.append(token.split("=", 1)[1])
        elif token == "--ignore" and index + 1 < len(tokens):
            ignored_paths.append(tokens[index + 1])
            index += 1
        index += 1
    return ignored_paths


def _excluded_tests(pytest_config: dict[str, Any]) -> list[dict[str, str]]:
    excluded: list[dict[str, str]] = []
    for path in pytest_config["ignored_paths"]:
        excluded.append(
            {
                "path": path,
                "reason": EXCLUDED_TEST_REASONS.get(
                    path,
                    "explicitly ignored in pyproject pytest addopts; requires separate documented validation",
                ),
            }
        )
    return excluded


def _claim_limitations(
    *,
    working_tree_clean: bool,
    full_repo_container_present: bool,
) -> list[str]:
    limitations = [
        "records local provenance only and does not create missing external evidence",
        "does not prove that live provider generations, recruited human annotations, pilot results, or telemetry were collected",
        "environment values are observed from the machine that produced the manifest",
    ]
    if not working_tree_clean:
        limitations.append(
            "working tree is dirty, so this is not a pinned release artifact"
        )
    if not full_repo_container_present:
        limitations.append(
            "no root repository container definition is present; only discovered container files are inventoried"
        )
    return limitations
