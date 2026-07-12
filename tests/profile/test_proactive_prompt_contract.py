"""Contract: proactive cron prompt must request gentle re-engagement.

Pins the proactive message contract so it stays distinct from both the
check-in question prompt and the diegetic life-fragment prompt.
"""
from __future__ import annotations

from relic.gumi_plugin.cron_wiring import render_proactive_message_prompt
from relic.profile.registry import ProfileRegistry


def _proactive_prompt() -> str:
    reg = ProfileRegistry.__new__(ProfileRegistry)
    return reg._cron_prompt_for_job({"task": "gumi_proactive_message", "output": ""})


def test_proactive_prompt_mentions_reengagement_and_receptivity():
    prompt = render_proactive_message_prompt().lower()
    assert "re-engagement" in prompt
    assert "recept" in prompt
    assert "unsolicited advice" in prompt
    assert "not needy" in prompt


def test_proactive_prompt_is_distinct_from_checkin_and_diegetic():
    reg = ProfileRegistry.__new__(ProfileRegistry)
    proactive_prompt = _proactive_prompt()
    checkin_prompt = reg._cron_prompt_for_job({"task": "gumi_checkin_message", "output": ""})
    diegetic_prompt = reg._cron_prompt_for_job({"task": "gumi_diegetic_message", "output": ""})

    assert proactive_prompt == render_proactive_message_prompt()
    assert proactive_prompt != checkin_prompt
    assert proactive_prompt != diegetic_prompt
    assert "battery" not in proactive_prompt.lower()
    assert "frammento di vita" not in proactive_prompt.lower()


def test_proactive_prompt_requires_specific_anchor():
    """Re-engagement must re-open one specific dropped thread, not a generic
    'come va?'; without an anchor the contract demands [SILENT]."""
    prompt = render_proactive_message_prompt()
    assert "ANCORA SPECIFICA" in prompt
    assert "[SILENT]" in prompt
    assert "come va?" in prompt  # pinned as a forbidden generic example


def test_proactive_prompt_media_exception_bypasses_silent_fallback():
    """Bug (3): voice/image/music CANDIDATE ticks always composed [SILENT]
    because the anchor-or-silent rule made no exception for media. The
    contract must now allow a small non-anchored gesture for media types,
    while text stays anchor-or-silent."""
    prompt = render_proactive_message_prompt()
    assert "ECCEZIONE MEDIA" in prompt
    assert "e il tipo è text" in prompt


def test_checkin_prompt_requires_facet_question_contract():
    reg = ProfileRegistry.__new__(ProfileRegistry)
    prompt = reg._cron_prompt_for_job({"task": "gumi_checkin_message", "output": ""}).lower()

    assert "ask_topic" in prompt
    assert "necessariamente una domanda" in prompt
    assert "rispondi esattamente [silent]" in prompt
