"""Contract: _cron_prompt_for_job for gumi_checkin_message must include
ask-mode handling and subject-context follow-up rule.

Pinning these strings prevents accidental regression to a Gumi-centric prompt
that ignores the subject and never asks questions.
"""
from __future__ import annotations

from relic.profile.registry import ProfileRegistry


def _checkin_prompt() -> str:
    reg = ProfileRegistry.__new__(ProfileRegistry)
    return reg._cron_prompt_for_job({"task": "gumi_checkin_message", "output": ""})


def test_prompt_mentions_ask_mode():
    p = _checkin_prompt()
    assert "ask: true" in p
    assert "ASK MODE" in p or "ask mode" in p.lower()
    assert "ask_topic" in p


def test_prompt_instructs_follow_up_on_subject():
    p = _checkin_prompt()
    assert "cosa ti ha detto di recente" in p


def test_prompt_warns_against_questions_outside_ask_mode():
    p = _checkin_prompt()
    assert "NON fare domande" in p


def test_prompt_drops_gumi_centric_framing():
    p = _checkin_prompt()
    # Old Gumi-centric line must not return
    assert "ispirate alla tua giornata" not in p


def test_prompt_keeps_silent_short_circuit():
    p = _checkin_prompt()
    assert "[SILENT]" in p


def test_prompt_describes_constraint_header_contract():
    p = _checkin_prompt()
    assert "[EVENTO:" in p
    assert "[POSTURA:" in p
    assert "[VINCOLI:" in p


def test_render_constraint_header_for_observe():
    from relic.checkin.policy import EventType, Posture, render_constraint_header

    header = render_constraint_header(EventType.CHECKIN, Posture.OBSERVE)
    assert "[EVENTO: checkin]" in header
    assert "[POSTURA: observe]" in header
    assert "[VINCOLI: max 1 frasi; senza domanda]" in header


def test_render_constraint_header_for_ask_marks_question():
    from relic.checkin.policy import EventType, Posture, render_constraint_header

    header = render_constraint_header(EventType.CHECKIN, Posture.ASK)
    assert "con domanda" in header
    assert "max 2 frasi" in header


def test_render_constraint_header_returns_empty_for_silent():
    from relic.checkin.policy import EventType, Posture, render_constraint_header

    assert render_constraint_header(EventType.SILENT, Posture.QUIET) == ""


def test_render_constraint_header_includes_grounding_when_provided():
    from relic.checkin.policy import EventType, Posture, render_constraint_header

    header = render_constraint_header(
        EventType.FOLLOWUP,
        Posture.FOLLOW_UP_WARM,
        grounding="esame venerdì",
    )
    assert "[GROUNDING: esame venerdì]" in header


def test_apply_constraint_header_prepends_to_message():
    from relic.checkin.policy import (
        Decision,
        EventType,
        Posture,
        apply_constraint_header,
    )

    decision = Decision(EventType.CHECKIN, Posture.OBSERVE, "test")
    out = apply_constraint_header("DELIVER\ntipo: text", decision)
    assert out.startswith("[EVENTO: checkin]\n[POSTURA: observe]\n")
    assert out.endswith("DELIVER\ntipo: text")
