"""PR04, RoleplayAdmissionController produces RoleplayAdmissionEvent."""
from __future__ import annotations

from relic.gumi_roleplay import RoleplayAdmissionController, RoleplayAdmissionEvent


def make_ctrl() -> RoleplayAdmissionController:
    return RoleplayAdmissionController()


class TestRoleplayAdmissionController:
    def test_high_stakes_task_gives_off(self):
        event = make_ctrl().evaluate(task_type="medical", consent=True)
        assert event.roleplay_level == "off"
        assert event.continuity_mode == "none"
        assert event.disclosure_required is True

    def test_legal_task_gives_off(self):
        event = make_ctrl().evaluate(task_type="legal", consent=True)
        assert event.roleplay_level == "off"

    def test_disable_roleplay_flag(self):
        event = make_ctrl().evaluate(task_type="relational", consent=True, disable_roleplay=True)
        assert event.roleplay_level == "off"
        assert "disable_roleplay_command" in event.reasons

    def test_no_consent_gives_off(self):
        event = make_ctrl().evaluate(task_type="relational", consent=False)
        assert event.roleplay_level == "off"

    def test_relational_with_consent_gives_light_or_normal(self):
        event = make_ctrl().evaluate(task_type="relational", consent=True)
        assert event.roleplay_level in ("light", "normal")

    def test_continuity_mode_none_when_no_candidates(self):
        event = make_ctrl().evaluate(
            task_type="relational", consent=True, continuity_candidates=[]
        )
        assert event.continuity_mode == "none"

    def test_continuity_mode_compact_with_candidates_light(self):
        event = make_ctrl().evaluate(
            task_type="relational",
            consent=True,
            continuity_candidates=[{"marker_id": "m1"}],
        )
        # light → compact, normal → expanded
        assert event.continuity_mode in ("compact", "expanded")

    def test_event_has_pack_id(self):
        event = make_ctrl().evaluate(pack_id="PCP-test-123", session_id="s1")
        assert event.pack_id == "PCP-test-123"
        assert event.session_id == "s1"

    def test_event_serializable(self):
        event = make_ctrl().evaluate(task_type="creative", consent=True)
        d = event.to_dict()
        assert "event_id" in d
        assert "roleplay_level" in d
        assert "created_at" in d

    def test_returns_roleplay_admission_event(self):
        event = make_ctrl().evaluate()
        assert isinstance(event, RoleplayAdmissionEvent)

    def test_technical_task_is_off_by_default(self):
        event = make_ctrl().evaluate(task_type="technical")
        assert event.roleplay_level == "off"
