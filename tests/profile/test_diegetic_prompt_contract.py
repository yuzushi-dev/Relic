"""Contract: diegetic cron prompt must request a positive, low-stakes life fragment.

Pins the diegetic message contract so it stays distinct from the check-in
question prompt and remains subject-safe.
"""
from __future__ import annotations

from relic.gumi_plugin.cron_wiring import render_diegetic_message_prompt
from relic.profile.registry import ProfileRegistry


def _diegetic_prompt() -> str:
    reg = ProfileRegistry.__new__(ProfileRegistry)
    return reg._cron_prompt_for_job({"task": "gumi_diegetic_message", "output": ""})


def test_diegetic_prompt_mentions_life_fragment_contract():
    prompt = render_diegetic_message_prompt()
    assert "frammento di vita" in prompt.lower()
    assert "positivo" in prompt.lower()
    assert "low-stakes" in prompt.lower()


def test_diegetic_prompt_is_distinct_from_checkin_prompt():
    reg = ProfileRegistry.__new__(ProfileRegistry)
    diegetic_prompt = _diegetic_prompt()
    checkin_prompt = reg._cron_prompt_for_job({"task": "gumi_checkin_message", "output": ""})

    assert diegetic_prompt == render_diegetic_message_prompt()
    assert diegetic_prompt != checkin_prompt
    assert "ask: true" not in diegetic_prompt
    assert "check-in naturale" not in diegetic_prompt


def test_diegetic_prompt_keeps_subject_out_of_scope():
    prompt = _diegetic_prompt()
    assert "NON parlare del soggetto" in prompt
    assert "prima persona" in prompt.lower()
