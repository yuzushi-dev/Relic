"""Unit tests for relic_humanness_analyst."""
import json
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from relic.relic_humanness_analyst import (
    EMDASH_RATE_WARN, EMDASH_RATE_CRIT,
    BULLET_RATE_WARN, BULLET_RATE_CRIT,
    BOT_PHRASE_RATE_WARN, BOT_PHRASE_RATE_CRIT,
    AFF_Q_RATE_WARN, AFF_Q_RATE_CRIT,
    LENGTH_RATIO_WARN, LENGTH_RATIO_CRIT,
    EMOJI_MONO_WARN, EMOJI_MONO_CRIT,
    _is_aff_q,
    score_bot_patterns,
    score_severity,
    select_worst_samples,
    format_report,
    apply_remediation,
    load_recent_agent_sessions,
    HUMANNESS_OVERRIDES_FILE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pair(user: str, agent: str) -> dict:
    return {"user": user, "agent": agent, "session": "test.jsonl"}


def _pairs(agent_msgs: list[str], user_msg: str = "ciao") -> list[dict]:
    return [_pair(user_msg, g) for g in agent_msgs]


# ── _is_aff_q ────────────────────────────────────────────────────────────────

def test_is_aff_q_true_for_long_statement_then_question():
    msg = "Sto riordinando sample e reference tra nomi provvisori. Come si fa a trovare il ritmo giusto?"
    assert _is_aff_q(msg) is True


def test_is_aff_q_false_for_short_pure_question():
    assert _is_aff_q("Come stai?") is False


def test_is_aff_q_false_for_statement_no_question():
    assert _is_aff_q("Oggi è stata una giornata bella.") is False


def test_is_aff_q_false_for_message_under_50_chars():
    assert _is_aff_q("Breve msg con domanda?") is False


def test_is_aff_q_true_with_newline_separator():
    msg = "Mi piace molto questo approccio.\nHai pensato a come applicarlo?"
    assert _is_aff_q(msg) is True


# ── score_bot_patterns ────────────────────────────────────────────────────────

def test_score_bot_patterns_empty_returns_error():
    assert "error" in score_bot_patterns([])


def test_score_bot_patterns_emdash():
    msgs = _pairs(["Ecco — un messaggio — con em dash — ovunque."] * 10)
    m = score_bot_patterns(msgs)
    assert m["emdash_rate"] > EMDASH_RATE_WARN
    assert m["emdash_count"] == 30


def test_score_bot_patterns_no_emdash():
    msgs = _pairs(["Messaggio normale senza trattini speciali."] * 10)
    m = score_bot_patterns(msgs)
    assert m["emdash_rate"] == 0.0


def test_score_bot_patterns_bullet():
    msgs = _pairs([
        "Ecco alcune opzioni:\n- Prima opzione\n- Seconda opzione",
        "Messaggio normale senza lista.",
        "Altro messaggio:\n• punto uno\n• punto due",
    ])
    m = score_bot_patterns(msgs)
    assert m["bullet_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["bullet_msgs"] == 2


def test_score_bot_patterns_bot_phrases():
    msgs = _pairs([
        "Certamente! Posso aiutarti con questo.",
        "Assolutamente, non esitare a chiedere.",
        "Messaggio normale senza frasi da bot.",
        "Un altro messaggio normale.",
    ])
    m = score_bot_patterns(msgs)
    assert m["bot_phrase_rate"] == pytest.approx(2 / 4, abs=1e-4)


def test_score_bot_patterns_aff_q():
    msgs = _pairs([
        "Ho pensato a lungo a questa cosa. Ti è capitato lo stesso?",
        "Sto lavorando su un progetto nuovo. Come procede il tuo?",
        "Ciao!",
        "Sì.",
    ])
    m = score_bot_patterns(msgs)
    assert m["aff_q_rate"] == pytest.approx(2 / 4, abs=1e-4)


def test_score_bot_patterns_length_ratio():
    pairs = [
        _pair("ok", "Questa è una risposta molto molto lunga che va avanti per molte parole senza sosta"),
        _pair("sì", "Anche questa risposta è piuttosto prolissa e continua ancora e ancora"),
    ]
    m = score_bot_patterns(pairs)
    assert m["avg_length_ratio"] > LENGTH_RATIO_WARN


def test_score_bot_patterns_emoji_monotony():
    msgs = _pairs([
        "Ciao! ✨",
        "Che bella giornata ✨",
        "Mi piace molto ✨",
        "Assolutamente ✨",
        "Benissimo ✨",
    ])
    m = score_bot_patterns(msgs)
    assert m["emoji_mono"] == pytest.approx(1.0, abs=1e-4)
    assert m["top_emoji"] == "✨"


def test_score_bot_patterns_emoji_variety():
    msgs = _pairs(["Ciao! ✨", "Bella 🌸", "Forza 💪", "Bene 😊", "Ok 🎵"])
    m = score_bot_patterns(msgs)
    assert m["emoji_mono"] < EMOJI_MONO_WARN


def test_score_bot_patterns_no_emoji():
    msgs = _pairs(["Messaggio senza emoji."] * 5)
    m = score_bot_patterns(msgs)
    assert m["emoji_mono"] == 0.0
    assert m["top_emoji"] == ""


# ── score_severity ────────────────────────────────────────────────────────────

def _base_metrics(**overrides) -> dict:
    base = {
        "emdash_rate": 0.0,
        "bullet_rate": 0.0,
        "bot_phrase_rate": 0.0,
        "aff_q_rate": 0.0,
        "avg_length_ratio": 1.0,
        "emoji_mono": 0.0,
    }
    base.update(overrides)
    return base


def test_score_severity_good():
    assert score_severity(_base_metrics()) == "good"


def test_score_severity_degraded_one_crit():
    assert score_severity(_base_metrics(emdash_rate=EMDASH_RATE_CRIT + 0.01)) == "degraded"


def test_score_severity_degraded_two_warns():
    m = _base_metrics(
        bullet_rate=BULLET_RATE_WARN + 0.01,
        bot_phrase_rate=BOT_PHRASE_RATE_WARN + 0.01,
    )
    assert score_severity(m) == "degraded"


def test_score_severity_critical_two_crits():
    m = _base_metrics(
        emdash_rate=EMDASH_RATE_CRIT + 0.01,
        bullet_rate=BULLET_RATE_CRIT + 0.01,
    )
    assert score_severity(m) == "critical"


def test_score_severity_degraded_single_warn():
    m = _base_metrics(aff_q_rate=AFF_Q_RATE_WARN + 0.01)
    assert score_severity(m) == "good"  # solo 1 warn = good


# ── select_worst_samples ──────────────────────────────────────────────────────

def test_select_worst_samples_returns_n():
    pairs = _pairs(["Messaggio normale."] * 20)
    samples = select_worst_samples(pairs, n=5)
    assert len(samples) == 5


def test_select_worst_samples_prefers_bot_msgs():
    pairs = [
        _pair("ciao", "— Certamente! Posso aiutarti:\n- opzione 1\n- opzione 2"),
        _pair("ciao", "Sì, capito."),
        _pair("ciao", "Anche questo è normale."),
    ]
    samples = select_worst_samples(pairs, n=1)
    assert "Certamente" in samples[0]["agent"]


def test_select_worst_samples_fewer_than_n():
    pairs = _pairs(["msg"] * 3)
    samples = select_worst_samples(pairs, n=10)
    assert len(samples) == 3


# ── format_report ─────────────────────────────────────────────────────────────

def _make_metrics(**kw) -> dict:
    return {
        "n_messages": 50,
        "emdash_rate": 0.12,
        "emdash_count": 5,
        "bullet_rate": 0.15,
        "bullet_msgs": 7,
        "bot_phrase_rate": 0.08,
        "bot_msgs": 4,
        "aff_q_rate": 0.45,
        "aff_q_msgs": 22,
        "avg_length_ratio": 2.3,
        "emoji_mono": 0.6,
        "top_emoji": "✨",
        **kw,
    }


def test_format_report_contains_status():
    report = format_report(_make_metrics(), [], "critical")
    assert "CRITICAL" in report


def test_format_report_contains_metrics():
    report = format_report(_make_metrics(), [], "degraded")
    assert "0.120" in report   # emdash_rate
    assert "15.0%" in report   # bullet_rate
    assert "45.0%" in report   # aff_q_rate


def test_format_report_shows_samples():
    samples = [_pair("domanda", "Agent risponde con — em dash e bullet:\n- a\n- b")]
    report = format_report(_make_metrics(), samples, "degraded")
    assert "Scambio 1" in report
    assert "User" in report
    assert "Agent" in report


def test_format_report_shows_rubric():
    samples = [_pair("x", "y")]
    report = format_report(_make_metrics(), samples, "degraded")
    assert "Naturale" in report
    assert "Proporzionato" in report
    assert "Continuo" in report
    assert "Diretto" in report


def test_format_report_good_status():
    report = format_report(_make_metrics(emdash_rate=0.0, bullet_rate=0.0), [], "good")
    assert "OK" in report


# ── apply_remediation ─────────────────────────────────────────────────────────

def test_apply_remediation_degraded_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("relic.relic_humanness_analyst.HUMANNESS_OVERRIDES_FILE",
                        tmp_path / "humanness_overrides.json")
    monkeypatch.setattr("relic.relic_humanness_analyst.RELIC_DIR", tmp_path)

    metrics = _make_metrics()
    apply_remediation(metrics, "degraded")

    f = tmp_path / "humanness_overrides.json"
    assert f.exists()
    data = json.loads(f.read_text())
    assert data["severity"] == "degraded"
    assert "—" in data.get("forbidden_phrases", [])
    assert data.get("no_bullet_points") is True
    assert data.get("no_mandatory_question") is True


def test_apply_remediation_critical_includes_emoji_cap(tmp_path, monkeypatch):
    monkeypatch.setattr("relic.relic_humanness_analyst.HUMANNESS_OVERRIDES_FILE",
                        tmp_path / "humanness_overrides.json")
    monkeypatch.setattr("relic.relic_humanness_analyst.RELIC_DIR", tmp_path)

    metrics = _make_metrics(emoji_mono=EMOJI_MONO_CRIT + 0.01)
    apply_remediation(metrics, "critical")
    data = json.loads((tmp_path / "humanness_overrides.json").read_text())
    assert data.get("emoji_cap") == 1


def test_apply_remediation_good_removes_file(tmp_path, monkeypatch):
    override_file = tmp_path / "humanness_overrides.json"
    override_file.write_text('{"severity":"degraded"}')
    monkeypatch.setattr("relic.relic_humanness_analyst.HUMANNESS_OVERRIDES_FILE", override_file)
    monkeypatch.setattr("relic.relic_humanness_analyst.RELIC_DIR", tmp_path)

    apply_remediation(_base_metrics(), "good")
    assert not override_file.exists()


def test_apply_remediation_good_no_file_no_error(tmp_path, monkeypatch):
    override_file = tmp_path / "humanness_overrides.json"
    monkeypatch.setattr("relic.relic_humanness_analyst.HUMANNESS_OVERRIDES_FILE", override_file)
    monkeypatch.setattr("relic.relic_humanness_analyst.RELIC_DIR", tmp_path)

    apply_remediation(_base_metrics(), "good")  # non deve sollevare eccezioni
    assert not override_file.exists()


def test_apply_remediation_length_ratio_sets_max_chars(tmp_path, monkeypatch):
    monkeypatch.setattr("relic.relic_humanness_analyst.HUMANNESS_OVERRIDES_FILE",
                        tmp_path / "humanness_overrides.json")
    monkeypatch.setattr("relic.relic_humanness_analyst.RELIC_DIR", tmp_path)

    metrics = _base_metrics(avg_length_ratio=LENGTH_RATIO_WARN + 0.5,
                            aff_q_rate=AFF_Q_RATE_WARN + 0.1)
    apply_remediation(metrics, "degraded")
    data = json.loads((tmp_path / "humanness_overrides.json").read_text())
    assert data.get("max_response_chars") == 350


# ── load_recent_agent_sessions ─────────────────────────────────────────────────

def _write_session(sessions_dir: Path, filename: str, messages: list[dict]) -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    with open(sessions_dir / filename, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def test_load_sessions_extracts_pairs(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir, "20260424_120000_abc.jsonl", [
        {"role": "user", "content": "Come stai?"},
        {"role": "assistant", "content": "Bene grazie!"},
        {"role": "user", "content": "E il progetto?"},
        {"role": "assistant", "content": "Va avanti."},
    ])
    pairs = load_recent_agent_sessions(tmp_path, days=30)
    assert len(pairs) == 2
    assert pairs[0]["user"] == "Come stai?"
    assert pairs[0]["agent"] == "Bene grazie!"


def test_load_sessions_skips_old_files(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir, "20200101_120000_old.jsonl", [
        {"role": "user", "content": "vecchio"},
        {"role": "assistant", "content": "risposta vecchia"},
    ])
    pairs = load_recent_agent_sessions(tmp_path, days=7)
    assert pairs == []


def test_load_sessions_handles_list_content(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir, "20260424_120000_abc.jsonl", [
        {"role": "user", "content": [{"type": "text", "text": "domanda"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "risposta"}]},
    ])
    pairs = load_recent_agent_sessions(tmp_path, days=30)
    assert len(pairs) == 1
    assert pairs[0]["agent"] == "risposta"


def test_load_sessions_skips_meta_role(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir, "20260424_120000_abc.jsonl", [
        {"role": "session_meta", "tools": []},
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "ciao a te"},
    ])
    pairs = load_recent_agent_sessions(tmp_path, days=30)
    assert len(pairs) == 1


def test_load_sessions_missing_dir_returns_empty(tmp_path):
    pairs = load_recent_agent_sessions(tmp_path, days=7)
    assert pairs == []
