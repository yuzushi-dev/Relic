"""Markdown docs stay out of the publishable repo root except README."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_DOCS = ROOT / "dev_docs" / "orchestration"
PROJECT_DOCS = ROOT / "dev_docs" / "project_docs"

ROOT_MARKDOWN = ["NORMATIVE_INDEX.md", "README.md"]

PROJECT_DOC_NAMES = [
    "ARCHITECTURE.md",
    "SECURITY.md",
    "EVALUATION.md",
    "REPLICATION.md",
    "ROADMAP.md",
    "DESIGN.md",
    "UI.md",
    "ACADEMIC_EVALUATION_PROTOCOL.md",
    "AGENT_DIARY_SCHEMA.md",
    "AGENT_WORLD_STATE_CONTRACT.md",
    "GUMI_BACKGROUND_GENERATION_PROTOCOL.md",
    "GUMI_CRON_SETUP.md",
    "GUMI_HERMES_ARCHITECTURE.md",
    "GUMI_HERMES_NATIVE_MEMORY_EVALUATION.md",
    "GUMI_INITIAL_CONTACT_PROTOCOL.md",
    "GUMI_ROLEPLAY_FRAME.md",
    "HERMES_COMPATIBILITY_REVIEW.md",
    "HUMAN_STUDY_INSTRUMENTS.md",
    "LITERATURE_POSITIONING_MATRIX.md",
    "LLM_BEHAVIOR_MODEL.md",
    "MEMORY_ASSOCIATION_GRAPH_CONTRACT.md",
    "MEMORY_CONSOLIDATION_CONTRACT.md",
    "MEMORY_DECAY_REINFORCEMENT_CONTRACT.md",
    "MEMORY_DYNAMICS_TAXONOMY.md",
    "PRIVACY_DPIA_DATA_MANAGEMENT.md",
    "PROMPT_CONTEXT_PACK_SCHEMA.md",
    "RELIC_MULTI_SUBJECT_PROFILE_CONTRACT.md",
    "ROLEPLAY_ADMISSION_POLICY.md",
    "ROLEPLAY_OUTPUT_CRITIC.md",
    "SECURITY_THREAT_MODEL.md",
    "UI_DEVELOPMENT_CHECKLIST.md",
    "UI_SCREEN_CONTRACTS.md",
    "UI_STATE_MATRIX.md",
    "UX_FLOWS.md",
    "UX_WRITING_GUIDELINES.md",
]

INTERNAL_DOCS = [
    "AGENTS.md",
    "TASKS.md",
    "TEST_MATRIX.md",
    "ORCHESTRATOR_BOOTSTRAP.md",
    "SUBAGENT_BOOTSTRAP.md",
    "SUBAGENT_TASK_PACKET_TEMPLATE.md",
    "ZERO_KNOWLEDGE_PR_FILE_CONTRACTS.md",
    "AUTONOMOUS_HANDOFF_RUNBOOK.md",
    "CI_WORKFLOW_CONTRACT.md",
    "MAKEFILE_TARGET_CONTRACT.md",
    "HERMES_BOOTSTRAP_CONTRACT.md",
    "CRON_SETUP_CONTRACT.md",
    "LOCAL_PRIVATE_DATA_TEST_CONTRACT.md",
    "TOOL_PERMISSION_MATRIX.md",
    "HERMES_PLUGIN_IMPLEMENTATION_PLAN.md",
    "DEBUG_BUNDLE.md",
    "BLUEPRINT_INTEGRATION_COMPATIBILITY.md",
    "HANDOFF_INTEGRATION_GUIDE.md",
    "INSTALLATION_AND_LOCAL_VERIFICATION_GUIDE.md",
    "INTEGRATION_REPO_REFERENCE_MATRIX.md",
    "ZERO_KNOWLEDGE_SUBAGENT_SETUP.md",
    "01_Relic_E2E_Core_Runtime.md",
    "02_Relic_E2E_Orchestration_Compiler_Safety.md",
    "03_Relic_E2E_Handoff_Codex_Claude.md",
    "04_Relic_E2E_Researcher_UI_Validation.md",
]


@pytest.mark.parametrize("filename", ROOT_MARKDOWN)
def test_allowed_root_markdown_present(filename: str) -> None:
    p = ROOT / filename
    assert p.exists(), f"missing root markdown entrypoint: {filename}"
    assert p.stat().st_size > 0, f"empty root markdown entrypoint: {filename}"


def test_no_extra_markdown_at_root() -> None:
    markdown_files = sorted(p.name for p in ROOT.glob("*.md"))
    assert markdown_files == ROOT_MARKDOWN


@pytest.mark.parametrize("filename", INTERNAL_DOCS)
def test_internal_doc_not_at_root(filename: str) -> None:
    assert not (ROOT / filename).exists(), f"internal doc should not be at repo root: {filename}"


@pytest.mark.parametrize("filename", INTERNAL_DOCS)
def test_internal_doc_present_in_dev_docs_when_available(filename: str) -> None:
    if not ORCHESTRATION_DOCS.exists():
        pytest.skip("dev_docs is intentionally gitignored and absent in publishable clones")
    p = ORCHESTRATION_DOCS / filename
    assert p.exists(), f"missing local handoff doc: {p}"
    assert p.stat().st_size > 0, f"empty local handoff doc: {p}"


@pytest.mark.parametrize("filename", PROJECT_DOC_NAMES)
def test_project_doc_moved_to_dev_docs_when_available(filename: str) -> None:
    assert not (ROOT / filename).exists(), f"project doc should not be at repo root: {filename}"
    if not PROJECT_DOCS.exists():
        pytest.skip("dev_docs is intentionally gitignored and absent in publishable clones")
    p = PROJECT_DOCS / filename
    assert p.exists(), f"missing local project doc: {p}"
    assert p.stat().st_size > 0, f"empty local project doc: {p}"
