"""Tests for skill metadata validation.

Acceptance criteria:
- skill files have version and owner
- skills cannot store user-specific facts
- skill candidate promotion is blocked in first iteration
"""

import re
from pathlib import Path
from typing import Any

import pytest

SKILLS_DIR = Path(__file__).parent.parent.parent / "contracts"
REQUIRED_SKILLS = [
    "relic-critique-calibration.md",
    "relic-correction-workflow.md",
    "relic-sensitive-context-handling.md",
    "relic-repair-response.md",
    "relic-model-boundary.md",
]

VERSION_PATTERN = re.compile(r"^\*\*Version:\*\*\s+(\d+\.\d+\.\d+)", re.MULTILINE)
OWNER_PATTERN = re.compile(r"^\*\*Owner:\*\*\s+(\S+)", re.MULTILINE)
STATUS_PATTERN = re.compile(r"^\*\*Status:\*\*\s+(\S+)", re.MULTILINE)

# Patterns for POSITIVE claims (should be present)
PROMOTION_BLOCK_PATTERNS = [
    re.compile(r"promotion\s+(?:is\s+)?blocked", re.IGNORECASE),
    re.compile(r"blocked\s+in\s+first\s+iteration", re.IGNORECASE),
    re.compile(r"first\s+iteration.*blocked", re.IGNORECASE),
]

# Negative patterns - self-promotion in positive context (should NOT be present)
# These must NOT match negated forms
SELF_PROMOTE_POSITIVE = re.compile(r"\bcan\s+(?:self[- ])?promot[ei]\b", re.IGNORECASE)

# Block condition patterns that indicate negation
BLOCK_CONDITION_PATTERNS = [
    re.compile(r"\*\*BLOCKED\*\*:\s*.*can\s+(?:self[- ])?promot", re.IGNORECASE | re.DOTALL),
]


def is_in_block_condition_context(text: str, match_start: int) -> bool:
    """Check if the match is in a block condition context (negated claim).

    Block conditions format: "- **BLOCKED**: Skill can promote itself to runtime provider"
    The pattern matches BLOCKED followed by "can promote" in the same context.
    """
    # Look at 200 chars around the match
    context_start = max(0, match_start - 50)
    context_end = min(len(text), match_start + 100)
    context = text[context_start:context_end]

    for pattern in BLOCK_CONDITION_PATTERNS:
        # Find all matches in context
        for block_match in pattern.finditer(context):
            # Check if our SELF_PROMOTE_POSITIVE match is within this block context
            block_start_in_context = block_match.start()
            block_end_in_context = block_match.end()
            match_pos_in_context = match_start - context_start

            # If the "can promote" is within the BLOCKED context
            if block_start_in_context <= match_pos_in_context <= block_end_in_context:
                return True
    return False


def load_skill_metadata(skill_path: Path) -> dict[str, Any]:
    """Load and parse skill metadata from a markdown file."""
    content = skill_path.read_text()

    version_match = VERSION_PATTERN.search(content)
    owner_match = OWNER_PATTERN.search(content)
    status_match = STATUS_PATTERN.search(content)

    return {
        "path": skill_path,
        "content": content,
        "version": version_match.group(1) if version_match else None,
        "owner": owner_match.group(1) if owner_match else None,
        "status": status_match.group(1) if status_match else None,
    }


class TestSkillMetadata:
    """Test suite for skill metadata validation."""

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_skill_file_exists(self, skill_file: str) -> None:
        """Verify each required skill file exists."""
        skill_path = SKILLS_DIR / skill_file
        assert skill_path.exists(), f"Required skill file missing: {skill_path}"

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_skill_has_version(self, skill_file: str) -> None:
        """Verify each skill has a properly formatted version field."""
        skill_path = SKILLS_DIR / skill_file
        metadata = load_skill_metadata(skill_path)

        assert metadata["version"] is not None, (
            f"Skill {skill_file} missing version field. Expected **Version:** X.Y.Z format."
        )

        version_parts = metadata["version"].split(".")
        assert len(version_parts) == 3, (
            f"Skill {skill_file} has malformed version: {metadata['version']}. "
            "Expected semantic version format X.Y.Z"
        )
        for part in version_parts:
            assert part.isdigit(), f"Skill {skill_file} has non-numeric version part: {part}"

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_skill_has_owner(self, skill_file: str) -> None:
        """Verify each skill has an owner field."""
        skill_path = SKILLS_DIR / skill_file
        metadata = load_skill_metadata(skill_path)

        assert metadata["owner"] is not None, (
            f"Skill {skill_file} missing owner field. Expected **Owner:** <owner-name> format."
        )

        assert metadata["owner"] != "", f"Skill {skill_file} has empty owner field."

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_skill_has_status(self, skill_file: str) -> None:
        """Verify each skill has a status field."""
        skill_path = SKILLS_DIR / skill_file
        metadata = load_skill_metadata(skill_path)

        assert metadata["status"] is not None, (
            f"Skill {skill_file} missing status field. Expected **Status:** <status> format."
        )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_skill_has_required_sections(self, skill_file: str) -> None:
        """Verify each skill has required documentation sections."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text()

        required_sections = ["Purpose", "Inputs", "Outputs", "Privacy Notes"]
        for section in required_sections:
            assert f"## {section}" in content or f"## {section.upper()}" in content, (
                f"Skill {skill_file} missing required section: {section}"
            )


class TestSkillCandidatePromotionBlocked:
    """Test suite for skill candidate promotion blocking.

    Acceptance criteria: skill candidate promotion is blocked in first iteration
    """

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_promotion_blocked_in_skill_content(self, skill_file: str) -> None:
        """Verify skills contain promotion blocking language."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text().lower()

        has_promotion_block = any(pattern.search(content) for pattern in PROMOTION_BLOCK_PATTERNS)

        assert has_promotion_block, (
            f"Skill {skill_file} missing promotion blocking language. "
            "Expected references to 'promotion blocked', 'first iteration', "
            "'runtime provider', or 'cannot promote itself'."
        )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_no_self_promotion_capability(self, skill_file: str) -> None:
        """Verify skills do not claim self-promotion capability (only block conditions)."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text()

        violations = []
        for match in SELF_PROMOTE_POSITIVE.finditer(content):
            # Skip matches in block condition context (they're negated/blocked)
            if is_in_block_condition_context(content, match.start()):
                continue
            violations.append(
                f"  - Unblocked capability at position {match.start()}: '{match.group()}'"
            )

        assert not violations, (
            f"Skill {skill_file} contains unblocked self-promotion capability. "
            f"Found:\n" + "\n".join(violations) + "\nSkills must NOT be able to promote themselves."
        )


class TestSkillPrivacyCompliance:
    """Test suite for skill privacy compliance.

    Block conditions:
    - skill stores user-specific preference
    """

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_has_privacy_notes_section(self, skill_file: str) -> None:
        """Verify skills have a Privacy Notes section."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text().lower()

        assert "privacy note" in content, (
            f"Skill {skill_file} missing Privacy Notes section. Expected ## Privacy Notes section."
        )


class TestSkillAcceptanceCriteria:
    """Comprehensive test for Acceptance criteria."""

    def test_all_required_skills_exist(self) -> None:
        """Verify all required skill files are present."""
        missing = [skill for skill in REQUIRED_SKILLS if not (SKILLS_DIR / skill).exists()]
        assert not missing, f"Missing required skill files: {missing}"

    def test_all_skills_have_valid_metadata(self) -> None:
        """Verify all skills have complete valid metadata."""
        invalid = []
        for skill_file in REQUIRED_SKILLS:
            skill_path = SKILLS_DIR / skill_file
            metadata = load_skill_metadata(skill_path)

            if metadata["version"] is None:
                invalid.append(f"{skill_file}: missing version")
            if metadata["owner"] is None:
                invalid.append(f"{skill_file}: missing owner")
            if metadata["status"] is None:
                invalid.append(f"{skill_file}: missing status")

        assert not invalid, f"Invalid metadata: {invalid}"

    def test_promotion_blocked_across_all_skills(self) -> None:
        """Verify promotion blocking is consistent across all skills."""
        failures = []

        for skill_file in REQUIRED_SKILLS:
            skill_path = SKILLS_DIR / skill_file
            content = skill_path.read_text().lower()

            has_block = any(pattern.search(content) for pattern in PROMOTION_BLOCK_PATTERNS)

            if not has_block:
                failures.append(skill_file)

        assert not failures, (
            f"Promotion blocking missing in: {failures}. All skills must block self-promotion."
        )
