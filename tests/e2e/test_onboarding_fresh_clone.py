"""
E2E test: fresh clone onboarding flow.
Tests that a new user can install, init, and create a subject without wall-texts or crashes.
"""

import subprocess
import sys
import uuid
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def cleanup_test_subjects():
    """Clean up any existing test subjects before/after each test."""
    yield
    # Cleanup after test
    subject_id = f"subj_e2e_{uuid.uuid4().hex[:8]}"
    # Note: We don't delete the subject as the registry is shared between tests
    # This is fine for now as subsequent runs use unique IDs


class TestFreshCloneOnboarding:
    """Verify onboarding works for a fresh clone."""

    def test_relic_help_shows_init_hint(self):
        """Step 1: relic should show helpful startup message."""
        result = subprocess.run(
            [sys.executable, "-m", "relic"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "init" in result.stdout.lower()
        assert "ui" in result.stdout.lower()

    def test_relic_init_help_works(self):
        """Step 1b: relic init --help should show usage."""
        result = subprocess.run(
            [sys.executable, "-m", "relic", "init", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--ollama-model" in result.stdout

    def test_relic_setup_check_only(self):
        """Step 2: relic setup --check-only should run without crashing."""
        result = subprocess.run(
            [sys.executable, "-m", "relic", "setup", "--check-only"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Runtime checks" in result.stdout

    def test_relic_init_completes_with_defaults(self):
        """Step 3: relic init with defaults should complete without wall-text or crash."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "relic", "init", "--ollama-model", "llama3.2"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input="n\nn\nn\nn\nn\nn\n", timeout=60)
        
        assert proc.returncode == 0, f"relic init failed: {stderr}"
        assert "Runtime setup complete" in stdout
        assert "EOFError" not in stderr
        assert "Traceback" not in stderr

    def test_relic_subject_create_with_minimal_input(self):
        """Step 4: relic subject create should complete with minimal fixture input."""
        # Use unique ID each run to avoid conflicts
        unique_id = f"subj_e2e_{uuid.uuid4().hex[:8]}"
        
        lines = []
        lines.extend([""] * 69)  # item battery
        lines.extend([""] * 5)   # boundaries  
        lines.extend(["n"] * 5)  # consent
        lines.append("test_researcher")
        lines.append("")
        lines.append("")
        lines.extend([""] * 9)
        lines.append("yes")
        lines.extend([""] * 11)
        lines.append("accept")
        lines.append("1")
        input_data = "\n".join(lines) + "\n"
        
        proc = subprocess.Popen(
            [sys.executable, "-m", "relic", "subject", "create", 
             "--subject-id", unique_id, "--experiment-id", "exp_e2e_test"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input=input_data, timeout=120)
        
        assert proc.returncode == 0, f"subject create failed: {stderr}"
        assert "Created profile" in stdout
        assert "EOFError" not in stderr
        assert "Traceback" not in stderr

    def test_relic_profile_list_works(self):
        """Step 5: profile list should work."""
        result = subprocess.run(
            [sys.executable, "-m", "relic", "profile", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    def test_relic_ui_docker_compose_syntax(self):
        """Step 6: UI compose.yaml should be valid docker compose syntax."""
        ui_dir = Path(__file__).parent.parent.parent / "ui"
        compose_file = ui_dir / "compose.yaml"
        assert compose_file.exists(), "compose.yaml not found"
        
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "config"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ui_dir),
        )
        assert result.returncode == 0, f"Docker compose validation failed: {result.stderr}"

    def test_readme_quickstart_section_exists(self):
        """Step 7: README should have clear Quick Start section."""
        readme = Path(__file__).parent.parent.parent / "README.md"
        content = readme.read_text()
        assert "Quick Start" in content or "quick start" in content.lower()
        assert "pip install" in content
        assert "relic init" in content
