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
