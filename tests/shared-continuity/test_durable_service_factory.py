"""Contract tests for the durable continuity-service factory wiring.

`get_continuity_service()` must return a durable SQLite-backed service when a
subject scope is resolvable (RELIC_SUBJECT_ID + existing subject home), so
confirmed markers survive process restart in the live gateway, and must fall
back to the in-process service otherwise (tests / unprovisioned contexts).
"""

from __future__ import annotations

import importlib

import relic.shared_continuity.service as svcmod


def _make_subject_home(tmp_path, subject_id: str):
    home = tmp_path / "relic_home"
    (home / "subjects" / subject_id).mkdir(parents=True)
    return home


def test_durable_service_wired_when_subject_scope_present(tmp_path, monkeypatch):
    home = _make_subject_home(tmp_path, "subj_durable")
    monkeypatch.setenv("RELIC_HOME", str(home))
    monkeypatch.setenv("RELIC_SUBJECT_ID", "subj_durable")
    svcmod._durable_services.clear()

    service = svcmod.get_continuity_service()
    assert service._repository is not None
    assert (home / "subjects" / "subj_durable" / "continuity.db").exists()


def test_confirmed_marker_survives_process_restart_via_factory(tmp_path, monkeypatch):
    home = _make_subject_home(tmp_path, "subj_restart")
    monkeypatch.setenv("RELIC_HOME", str(home))
    monkeypatch.setenv("RELIC_SUBJECT_ID", "subj_restart")
    svcmod._durable_services.clear()

    first = svcmod.get_continuity_service()
    marker = first.remember(
        subject_id="subj_restart",
        gumi_instance_id="g",
        hermes_profile_id="h",
        subject_words=["the hum"],
        source_type="subject_confirmed",
        subject_confirmation=True,
    )

    # Simulate a gateway restart: drop the per-process cache so the next
    # resolution rebuilds the service and reloads state from continuity.db.
    svcmod._durable_services.clear()
    restarted = svcmod.get_continuity_service()
    assert restarted is not first

    recalled = restarted.recent_markers(subject_id="subj_restart")
    assert [item["marker_id"] for item in recalled] == [marker["marker_id"]]
    assert recalled[0]["subject_words"] == ["the hum"]


def test_falls_back_to_in_memory_without_subject_scope(tmp_path, monkeypatch):
    monkeypatch.delenv("RELIC_SUBJECT_ID", raising=False)
    svcmod._durable_services.clear()

    service = svcmod.get_continuity_service()
    assert service is svcmod._service
    assert service._repository is None


def test_falls_back_to_in_memory_when_subject_home_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path / "relic_home"))
    monkeypatch.setenv("RELIC_SUBJECT_ID", "never_provisioned")
    svcmod._durable_services.clear()

    service = svcmod.get_continuity_service()
    assert service is svcmod._service
    assert service._repository is None
