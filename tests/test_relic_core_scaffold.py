from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_relic_core_package_exists() -> None:
    pkg = ROOT / "src" / "relic_core"
    assert pkg.exists()
    assert (pkg / "__init__.py").exists()
    assert (pkg / "db.py").exists()
    assert (pkg / "inbox.py").exists()
    assert (pkg / "portrait.py").exists()
    assert (pkg / "question_engine.py").exists()
    assert (pkg / "synthesizer.py").exists()


def test_relic_core_reexports_current_modules() -> None:
    from relic_core.db import RelicDB  # type: ignore
    from relic_core.inbox import append_to_inbox  # type: ignore
    from relic_core.portrait import render_layer4_portrait  # type: ignore
    from relic_core.question_engine import select_checkin_facets  # type: ignore
    from relic_core.synthesizer import synthesize_all_traits  # type: ignore

    assert RelicDB is not None
    assert append_to_inbox is not None
    assert render_layer4_portrait is not None
    assert select_checkin_facets is not None
    assert synthesize_all_traits is not None


def test_runtime_interface_contracts_exist() -> None:
    interfaces = ROOT / "src" / "relic_core" / "interfaces"
    assert interfaces.exists()
    assert (interfaces / "__init__.py").exists()
    assert (interfaces / "contracts.py").exists()

    from relic_core.interfaces import (  # type: ignore
        ArtifactGate,
        ArtifactPublisher,
        DeliverySink,
        MessageSource,
        ModelBackend,
        SchedulerBinding,
        SessionSource,
    )

    assert MessageSource is not None
    assert SessionSource is not None
    assert DeliverySink is not None
    assert SchedulerBinding is not None
    assert ModelBackend is not None
    assert ArtifactPublisher is not None
    assert ArtifactGate is not None


def test_scaffold_and_bridge_adrs_exist() -> None:
    scaffold_adr = ROOT / "docs" / "adrs" / "2026-04-19-relic-core-scaffold-decision.md"
    bridge_adr = ROOT / "docs" / "adrs" / "2026-04-19-bridge-contract-v1.md"

    assert scaffold_adr.exists()
    assert bridge_adr.exists()

