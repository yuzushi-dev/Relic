from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_relic_hermes_adapter_package_exists() -> None:
    pkg = ROOT / "src" / "relic_hermes" / "adapters"
    assert pkg.exists()
    assert (pkg / "__init__.py").exists()
    assert (pkg / "session_source.py").exists()
    assert (pkg / "scheduler.py").exists()


def test_relic_hermes_exports_adapter_entrypoints() -> None:
    from relic_hermes.adapters import HermesCronBinding, HermesSessionSource  # type: ignore

    assert HermesSessionSource is not None
    assert HermesCronBinding is not None
