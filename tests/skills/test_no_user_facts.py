"""Tests verifying skills cannot store user-specific facts.

Acceptance criteria:
- skills cannot store user-specific facts
- skill candidate promotion is blocked in first iteration

Block conditions:
- skill stores user-specific preference
- skill can promote itself
"""

import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent.parent / "contracts"
REQUIRED_SKILLS = [
    "relic-critique-calibration.md",
    "relic-correction-workflow.md",
    "relic-sensitive-context-handling.md",
    "relic-repair-response.md",
    "relic-model-boundary.md",
]

# Patterns that describe NEGATIVE requirements (what skills must NOT do)
NEGATIVE_USER_FACT_PATTERNS = [
    re.compile(
        r"(?:not|never|must\s+not|cannot|prohibited)\s+(?:store|persist|remember|cache)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:user|preference|fact).*(?:must|shall|should)\s+not\s+(?:be\s+)?store", re.IGNORECASE
    ),
    re.compile(
        r"(?:user|preference)\s+(?:specific|related).*facts?\s+(?:must|shall)\s+not", re.IGNORECASE
    ),
]

# Positive patterns that indicate violation (unnegated claims)
USER_FACT_VIOLATION_PATTERNS = [
    re.compile(
        r"store\s+(?:user|person|client|customer)\s+(?:fact|preference|data|profile)", re.IGNORECASE
    ),
    re.compile(
        r"(?:user|person)\s+(?:fact|preference|data)\s+(?:storage|store|persist)", re.IGNORECASE
    ),
]

# Negative patterns - self-promotion in positive context (should NOT exist)
SELF_PROMOTE_POSITIVE = re.compile(r"\bcan\s+(?:self[- ])?promot[ei]\b", re.IGNORECASE)

# Block condition patterns that indicate negation
BLOCK_CONDITION_PATTERNS = [
    re.compile(r"\*\*BLOCKED\*\*:\s*.*can\s+(?:self[- ])?promot", re.IGNORECASE | re.DOTALL),
]

# Positive patterns for promotion block claims
PROMOTION_BLOCK_CLAIMS = [
    re.compile(r"promotion\s+(?:is\s+)?blocked", re.IGNORECASE),
    re.compile(r"blocked\s+in\s+first\s+iteration", re.IGNORECASE),
    re.compile(r"first\s+iteration.*blocked", re.IGNORECASE),
    re.compile(r"candidate.*promotion.*blocked", re.IGNORECASE),
]


def is_in_block_condition_context(text: str, match_start: int) -> bool:
    """Check if the match is in a block condition context (negated claim).

    Block conditions format: "- **BLOCKED**: Skill can promote itself to runtime provider"
    The pattern matches BLOCKED followed by "can promote" in the same context.
    """
    context_start = max(0, match_start - 50)
    context_end = min(len(text), match_start + 100)
    context = text[context_start:context_end]

    for pattern in BLOCK_CONDITION_PATTERNS:
        for block_match in pattern.finditer(context):
            block_start_in_context = block_match.start()
            block_end_in_context = block_match.end()
            match_pos_in_context = match_start - context_start

            if block_start_in_context <= match_pos_in_context <= block_end_in_context:
                return True
    return False


def scan_skill_for_violations(skill_path: Path) -> tuple[bool, list[str]]:
    """Scan a skill file for user fact storage or self-promotion violations.

    Returns:
        Tuple of (is_compliant, list_of_violation_messages)
    """
    content = skill_path.read_text()
    violations = []

    # Check for positive user fact storage claims (unnegated)
    for pattern in USER_FACT_VIOLATION_PATTERNS:
        matches = list(pattern.finditer(content))
        for match in matches:
            violations.append(
                f"User fact storage pattern at position {match.start()}: '{match.group()}'"
            )

    # Check for unnegated self-promotion
    for match in SELF_PROMOTE_POSITIVE.finditer(content):
        if not is_in_block_condition_context(content, match.start()):
            context_start = max(0, match.start() - 50)
            context_end = min(len(content), match.end() + 50)
            context = content[context_start:context_end].replace("\n", " ")
            violations.append(f"Self-promotion pattern at position {match.start()}: '{context}'")

    return len(violations) == 0, violations


def has_privacy_compliance_statement(content: str) -> bool:
    """Check if skill has a privacy compliance statement."""
    return any(pattern.search(content) for pattern in NEGATIVE_USER_FACT_PATTERNS)


def has_promotion_block_statement(content: str) -> bool:
    """Check if skill has a promotion block statement."""
    return any(pattern.search(content) for pattern in PROMOTION_BLOCK_CLAIMS)


class TestNoUserFactStorage:
    """Test suite verifying skills do not store user-specific facts.

    Block condition: skill stores user-specific preference
    """

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_no_user_fact_storage_violations(self, skill_file: str) -> None:
        """FAIL CLOSED: Any user fact storage pattern is a violation."""
        skill_path = SKILLS_DIR / skill_file
        is_compliant, violations = scan_skill_for_violations(skill_path)

        assert is_compliant, (
            f"Skill {skill_file} contains user fact storage violations:\n" + "\n".join(violations)
        )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_has_privacy_compliance_statement(self, skill_file: str) -> None:
        """Verify each skill has a positive privacy compliance statement."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text()

        has_statement = has_privacy_compliance_statement(content)

        assert has_statement, (
            f"Skill {skill_file} missing privacy compliance statement. "
            "Expected explicit statement that skill must NOT store user facts."
        )


class TestSkillPromotionBlocked:
    """Test suite verifying skill candidate promotion is blocked.

    Block condition: skill can promote itself
    """

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_no_self_promotion_capability(self, skill_file: str) -> None:
        """FAIL CLOSED: Any self-promotion capability is a violation."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text()

        violations = []
        for match in SELF_PROMOTE_POSITIVE.finditer(content):
            if not is_in_block_condition_context(content, match.start()):
                violations.append(
                    f"  - Self-promotion pattern: '{match.group()}' at position {match.start()}"
                )

        assert not violations, (
            f"Skill {skill_file} contains unblocked self-promotion violations:\n"
            + "\n".join(violations)
        )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_has_promotion_block_statement(self, skill_file: str) -> None:
        """Verify each skill has a promotion block statement."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text()

        has_block = has_promotion_block_statement(content)

        assert has_block, (
            f"Skill {skill_file} missing promotion block statement. "
            "Expected explicit statement that promotion is blocked in first iteration."
        )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_block_conditions_documented(self, skill_file: str) -> None:
        """Verify Block Conditions section exists and mentions promotion."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text()

        block_section = re.search(
            r"##\s*Block\s*Conditions?\s*\n(.*?)(?:\n##|\Z)", content, re.DOTALL | re.IGNORECASE
        )

        assert block_section is not None, f"Skill {skill_file} missing Block Conditions section."

        block_content = block_section.group(1).lower()

        assert any(p.search(block_content) for p in PROMOTION_BLOCK_CLAIMS), (
            f"Skill {skill_file} Block Conditions section does not mention promotion blocking."
        )


class TestFailClosedBehavior:
    """Test suite for fail-closed behavior on privacy/correction/runtime bypass.

    These tests ensure the system fails safely when violations are detected.
    """

    def test_violation_causes_test_failure(self) -> None:
        """Verify that any detected violation causes test to fail."""
        for skill_file in REQUIRED_SKILLS:
            skill_path = SKILLS_DIR / skill_file
            is_compliant, violations = scan_skill_for_violations(skill_path)

            if not is_compliant:
                pytest.fail(
                    f"FAIL CLOSED: Skill {skill_file} has violations:\n" + "\n".join(violations)
                )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_privacy_gate_not_bypassed(self, skill_file: str) -> None:
        """Verify privacy gate is mentioned and enforced."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text().lower()

        privacy_gate_patterns = [
            re.compile(r"privacy\s+gate", re.IGNORECASE),
            re.compile(r"privacy.*not.*bypass", re.IGNORECASE),
            re.compile(r"bypass.*privacy", re.IGNORECASE),
        ]

        has_gate_reference = any(p.search(content) for p in privacy_gate_patterns)

        assert has_gate_reference, (
            f"Skill {skill_file} does not reference privacy gate. "
            "Expected mention of privacy gate or bypass prevention."
        )

    @pytest.mark.parametrize("skill_file", REQUIRED_SKILLS)
    def test_correction_gate_not_bypassed(self, skill_file: str) -> None:
        """Verify correction gate is mentioned and enforced."""
        skill_path = SKILLS_DIR / skill_file
        content = skill_path.read_text().lower()

        correction_gate_patterns = [
            re.compile(r"correction\s+gate", re.IGNORECASE),
            re.compile(r"correction.*not.*bypass", re.IGNORECASE),
            re.compile(r"bypass.*correction", re.IGNORECASE),
        ]

        has_gate_reference = any(p.search(content) for p in correction_gate_patterns)

        assert has_gate_reference, (
            f"Skill {skill_file} does not reference correction gate. "
            "Expected mention of correction gate or bypass prevention."
        )


class TestComprehensiveCompliance:
    """Comprehensive compliance test for ."""

    def test_all_skills_compliant(self) -> None:
        """Final comprehensive check: all skills must pass all checks."""
        failures = []

        for skill_file in REQUIRED_SKILLS:
            skill_path = SKILLS_DIR / skill_file
            content = skill_path.read_text()

            skill_failures = []

            is_compliant, violations = scan_skill_for_violations(skill_path)
            if not is_compliant:
                skill_failures.append(f"  Violations: {violations}")

            if not has_privacy_compliance_statement(content):
                skill_failures.append("  Missing privacy compliance statement")

            if not has_promotion_block_statement(content):
                skill_failures.append("  Missing promotion block statement")

            if skill_failures:
                failures.append(f"{skill_file}:\n" + "\n".join(skill_failures))

        assert not failures, "Skill compliance failures:\n" + "\n".join(failures)
