"""Smoke tests for relic skeleton, no runtime behavior."""

import subprocess
import sys


def test_cli_smoke():
    """CLI version/smoke output only, no runtime behavior."""
    result = subprocess.run(
        [sys.executable, "-m", "relic.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "relic" in result.stdout


def test_import_relic():
    """relic package is importable."""
    import relic
    assert hasattr(relic, "__version__")


def test_relic_module_structure():
    """Package has expected module files."""
    from pathlib import Path
    relic_path = Path(__file__).parent.parent / "relic"
    assert (relic_path / "__init__.py").exists()
    assert (relic_path / "cli.py").exists()
