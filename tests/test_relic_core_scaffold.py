from importlib import import_module
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_relic_core_package_scaffold_exists():
    package_dir = ROOT / "src" / "relic_core"
    assert package_dir.exists()
    assert (package_dir / "__init__.py").exists()


def test_relic_core_exposes_first_boundary_modules():
    package = import_module("relic_core")
    assert package.__all__ == [
        "db",
        "inbox",
        "portrait",
        "question_engine",
        "synthesizer",
    ]

    assert import_module("relic_core.db")
    assert import_module("relic_core.inbox")
    assert import_module("relic_core.portrait")
    assert import_module("relic_core.question_engine")
    assert import_module("relic_core.synthesizer")
