#!/usr/bin/env python3
"""Run the local scientific claim-readiness workflow and write a run report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_ID = "scientific_claim_readiness_run_v1"
CLAIM_SCOPE = "local_claim_readiness_workflow_execution"
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    command: tuple[str, ...]
    artifact_path: Path | None = None
    expected_nonzero: bool = False
    purpose: str = ""


def build_plan(*, output_dir: Path, mode: str) -> list[WorkflowStep]:
    """Build the ordered local claim-readiness workflow."""
    python = sys.executable
    output_dir = output_dir.resolve()
    plan = [
        WorkflowStep(
            step_id="scientific_environment_manifest",
            command=(
                python,
                "scripts/eval_run.py",
                "--experiment",
                "scientific_environment_manifest",
                "--output",
                str(output_dir / "scientific-environment-manifest.json"),
                "--json",
            ),
            artifact_path=output_dir / "scientific-environment-manifest.json",
            purpose="records local environment provenance and release-artifact readiness",
        ),
        WorkflowStep(
            step_id="scientific_reproducibility_snapshot",
            command=(
                python,
                "scripts/eval_run.py",
                "--experiment",
                "scientific_reproducibility_snapshot",
                "--output",
                str(output_dir / "scientific-reproducibility-snapshot.json"),
                "--json",
            ),
            artifact_path=output_dir / "scientific-reproducibility-snapshot.json",
            purpose="hashes locally reproducible reports and expected outputs",
        ),
        WorkflowStep(
            step_id="scientific_observation_remediation_audit",
            command=(
                python,
                "scripts/eval_run.py",
                "--experiment",
                "scientific_observation_remediation_audit",
                "--output",
                str(output_dir / "scientific-observation-remediation-audit.json"),
                "--json",
            ),
            artifact_path=output_dir / "scientific-observation-remediation-audit.json",
            purpose="maps the observation packet gaps to current evidence and remaining blockers",
        ),
        WorkflowStep(
            step_id="mock_runtime_telemetry_campaign",
            command=(
                python,
                "scripts/eval_run.py",
                "--experiment",
                "mock_runtime_telemetry_campaign",
                "--output",
                str(output_dir / "mock-runtime-telemetry-campaign.json"),
                "--json",
            ),
            artifact_path=output_dir / "mock-runtime-telemetry-campaign.json",
            purpose="generates deterministic mock-gateway runtime telemetry evidence",
        ),
        WorkflowStep(
            step_id="scientific_local_evidence_package",
            command=(
                python,
                "scripts/eval_run.py",
                "--experiment",
                "scientific_local_evidence_package",
                "--output",
                str(output_dir / "scientific-local-evidence-package.json"),
                "--json",
            ),
            artifact_path=output_dir / "scientific-local-evidence-package.json",
            expected_nonzero=True,
            purpose="runs the gate with only local synthetic evidence and records remaining blockers",
        ),
    ]

    if mode == "full":
        plan.extend(_full_verification_steps(output_dir=output_dir))

    plan.append(
        WorkflowStep(
            step_id="scientific_defensibility_gate",
            command=(
                python,
                "scripts/eval_run.py",
                "--experiment",
                "scientific_defensibility_gate",
                "--output",
                str(output_dir / "scientific-defensibility-gate.json"),
                "--json",
            ),
            artifact_path=output_dir / "scientific-defensibility-gate.json",
            expected_nonzero=True,
            purpose="executes the conservative broad-claim readiness gate",
        )
    )
    return plan


def run_workflow(*, output_dir: Path, mode: str) -> dict[str, Any]:
    """Run the workflow and return a machine-readable report."""
    output_dir = output_dir.resolve()
    logs_dir = output_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    step_reports: list[dict[str, Any]] = []
    for step in build_plan(output_dir=output_dir, mode=mode):
        result = subprocess.run(
            step.command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        stdout_path = logs_dir / f"{step.step_id}.stdout"
        stderr_path = logs_dir / f"{step.step_id}.stderr"
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        step_reports.append(_step_report(step, result, stdout_path, stderr_path))

    unexpected_failures = [
        step for step in step_reports if step["status"] == "failed"
    ]
    expected_blocks = [
        step for step in step_reports if step["status"] == "expected_block"
    ]
    overall_status = (
        "failed"
        if unexpected_failures
        else "blocked"
        if expected_blocks
        else "passed"
    )
    report = {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "mode": mode,
        "output_dir": str(output_dir),
        "overall_status": overall_status,
        "summary": {
            "step_count": len(step_reports),
            "artifact_file_count": sum(1 for step in step_reports if step["artifact_exists"]),
            "expected_block_count": len(expected_blocks),
            "unexpected_failure_count": len(unexpected_failures),
            "blocks_scientific_claims": overall_status in {"blocked", "failed"},
        },
        "steps": step_reports,
        "claim_limitations": [
            "local workflow execution does not create recruited human or live-provider evidence",
            "blocked status is expected until the scientific_defensibility_gate requirements are satisfied",
            "full mode is required before release packaging; smoke mode is a quick artifact exercisability check",
            (
                "the gate appears at different counts by evidence scope, not by contradiction: "
                "scientific_defensibility_gate with no bundle = 1/7 (benchmark only); "
                "scientific_local_evidence_package = 2/7 (adds code-generated mock telemetry); "
                "the committed live-model + telemetry evidence reaches 3/7 via "
                "`make gate` / `scripts/gate_local_evidence.py`. 3/7 is the local maximum; "
                "requirements 4-7 require recruited human data"
            ),
        ],
    }
    (output_dir / "scientific-claim-readiness-run.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local scientific claim-readiness workflow")
    parser.add_argument(
        "--mode",
        choices=["smoke", "full"],
        default="smoke",
        help=(
            "smoke (default) generates the core reports + gate; "
            "full also runs the broad pytest-cov surface and a docker build "
            "(heavy: requires uv + docker, can OOM on small machines) and is "
            "required only before release packaging"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/scientific-claim-readiness"),
        help="Directory for generated reports and command logs",
    )
    parser.add_argument("--json", action="store_true", help="Print run report JSON")
    args = parser.parse_args(argv)

    report = run_workflow(output_dir=args.output_dir, mode=args.mode)
    if args.json:
        print(json.dumps(report, indent=2))
    return 0 if report["overall_status"] == "passed" else 1


def _full_verification_steps(*, output_dir: Path) -> list[WorkflowStep]:
    commit = _git_value(["rev-parse", "HEAD"]) or "unknown"
    branch = _git_value(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    return [
        WorkflowStep(
            step_id="compileall",
            command=(sys.executable, "-m", "compileall", "relic", "scripts", "tests/eval"),
            purpose="checks Python compilation for the evaluation surface",
        ),
        WorkflowStep(
            step_id="privacy_marker_scan",
            command=(sys.executable, "scripts/ci/check_no_raw_private_data.py"),
            purpose="checks that private/raw data markers are not introduced",
        ),
        WorkflowStep(
            step_id="diff_check",
            command=("git", "diff", "--check"),
            purpose="checks patch whitespace and diff hygiene",
        ),
        WorkflowStep(
            step_id="broad_pytest_scientific_surface",
            command=(
                "uv",
                "run",
                "--extra",
                "dev",
                "pytest",
                "--import-mode=importlib",
                "--cov=relic",
                "--cov=scripts",
                f"--cov-report=json:{output_dir / 'scientific-surface-coverage.json'}",
                "--cov-report=term-missing:skip-covered",
                "tests/eval",
                "tests/gumi-eval",
                "tests/gumi_plugin",
                "tests/hermes_plugin",
                "tests/hermes_compat",
                "tests/test_db_schema.py",
                "-q",
            ),
            artifact_path=output_dir / "scientific-surface-coverage.json",
            purpose="runs broad evaluation, Gumi, Hermes, compatibility, and DB regression surface",
        ),
        WorkflowStep(
            step_id="docker_build_scientific_environment",
            command=(
                "docker",
                "build",
                "--build-arg",
                f"RELIC_SOURCE_COMMIT={commit}",
                "--build-arg",
                f"RELIC_SOURCE_BRANCH={branch}",
                "-t",
                "relic-scientific-eval:local",
                ".",
            ),
            purpose="builds the root containerized scientific evaluation environment",
        ),
    ]


def _step_report(
    step: WorkflowStep,
    result: subprocess.CompletedProcess[str],
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    status = "passed"
    if result.returncode != 0 and step.expected_nonzero:
        status = "expected_block"
    elif result.returncode != 0:
        status = "failed"
    return {
        "step_id": step.step_id,
        "purpose": step.purpose,
        "command": list(step.command),
        "exit_code": result.returncode,
        "expected_nonzero": step.expected_nonzero,
        "status": status,
        "artifact_path": str(step.artifact_path) if step.artifact_path else None,
        "artifact_exists": bool(step.artifact_path and step.artifact_path.exists()),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _git_value(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


if __name__ == "__main__":
    sys.exit(main())
