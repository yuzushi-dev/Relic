"""relic_debate — Pro/Contra/Judge LLM debate for analyst modules.

Shared by health_monitor, humanness_analyst, and biofeedback_correlation.
Each analyst calls run_debate() after computing metrics to produce a structured
internal debate before submitting to the Paperclip reviewer.

Models (all default to openrouter/free):
  Pro:    RELIC_<DOMAIN>_PRO_MODEL   → RELIC_INQUIRY_PRO_MODEL   → default
  Contra: RELIC_<DOMAIN>_CONTRA_MODEL→ RELIC_INQUIRY_CONTRA_MODEL → default
  Judge:  RELIC_<DOMAIN>_JUDGE_MODEL → RELIC_INQUIRY_MODEL        → default
  Fallbacks: RELIC_<DOMAIN>_<ROLE>_FALLBACK_MODELS →
             RELIC_INQUIRY_FALLBACK_MODELS → built-in free fallbacks
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from lib.llm_resilience import chat_completion_content
from lib.log import warn

_DEFAULT_FREE = "openrouter/free"
_DEFAULT_FALLBACKS = (
    "qwen3.5:397b-cloud",
    "nvidia/meta/llama-3.3-70b-instruct",
    "smollm2:1.7b-instruct-q3_K_S",
)

# Maps Judge verdict to override severity. None = no override. "clear" = remove override.
VERDICT_TO_SEVERITY: dict[str, str | None] = {
    "intervene_strong": "critical",
    "intervene_soft":   "degraded",
    "monitor":          None,
    "no_action":        "clear",
}


def verdict_to_severity(verdict: str) -> str | None:
    """Return override severity for a debate verdict, or None to skip."""
    return VERDICT_TO_SEVERITY.get(verdict)

_LLM_TIMEOUT = 90

_SYSTEM_PROMPTS: dict[str, dict[str, str]] = {
    "health": {
        "pro": (
            "You are an expert psychological data quality analyst. "
            "Argue that the metrics provided indicate a real degradation requiring intervention. "
            "Be specific: cite metric values and thresholds. Do NOT hedge."
        ),
        "contra": (
            "You are a cautious psychological data quality analyst. "
            "Argue that intervention may be premature. "
            "Consider: Is the trend improving? Are metrics borderline? Is sample size adequate? "
            "Identify confounds or alternative explanations."
        ),
        "judge": (
            "You are a senior data quality reviewer. "
            "You have read Pro and Contra arguments about health metrics. "
            "Synthesize and output STRICT JSON only:\n"
            '{"verdict": "<intervene_strong|intervene_soft|monitor|no_action>", '
            '"rationale": "<2 sentences>", "confidence": <0.0-1.0>}'
        ),
    },
    "humanness": {
        "pro": (
            "You are an expert in conversational AI naturalness assessment. "
            "Argue that the patterns in the AI companion's messages indicate it is sounding "
            "artificial, robotic, or sycophantic and needs correction. "
            "Cite specific patterns from the metrics and sample messages."
        ),
        "contra": (
            "You are a conversational AI naturalness reviewer. "
            "Argue that the flagged patterns may be within natural variation or contextually appropriate. "
            "Consider: Does the context justify these patterns? Are the sample sizes sufficient? "
            "Could this be the AI's genuine style rather than a bug?"
        ),
        "judge": (
            "You are a senior conversational AI evaluator. "
            "You have read Pro and Contra arguments about naturalness patterns. "
            "Synthesize and output STRICT JSON only:\n"
            '{"verdict": "<intervene_strong|intervene_soft|monitor|no_action>", '
            '"rationale": "<2 sentences>", "confidence": <0.0-1.0>}'
        ),
    },
    "bio": (
        {
            "pro": (
                "You are an expert in psychophysiological correlation analysis. "
                "Argue that the biofeedback correlation results are statistically robust "
                "and represent real signal. Cite rho values, p-values, and sample sizes. "
                "Argue that divergences represent meaningful signal shifts."
            ),
            "contra": (
                "You are a skeptical biostatistician. "
                "Challenge the validity of the correlations. Consider: "
                "Are sample sizes near the minimum threshold? Are there multiple comparison issues? "
                "Could divergences be noise? Are there alternative explanations?"
            ),
            "judge": (
                "You are a senior psychophysiology researcher. "
                "You have read Pro and Contra arguments about biofeedback correlations. "
                "Synthesize and output STRICT JSON only:\n"
                '{"verdict": "<intervene_strong|intervene_soft|monitor|no_action>", '
                '"rationale": "<2 sentences>", "confidence": <0.0-1.0>}'
            ),
        }
    ),
}


def _get_model(domain: str, role: str) -> str:
    domain_upper = domain.upper()
    role_upper = role.upper()
    # Per-domain override takes priority
    env_key = f"RELIC_{domain_upper}_{role_upper}_MODEL"
    if role == "judge":
        # Judge uses RELIC_<DOMAIN>_JUDGE_MODEL or RELIC_INQUIRY_MODEL
        val = os.environ.get(env_key) or os.environ.get("RELIC_INQUIRY_MODEL", _DEFAULT_FREE)
    elif role == "pro":
        val = os.environ.get(env_key) or os.environ.get("RELIC_INQUIRY_PRO_MODEL", _DEFAULT_FREE)
    else:
        val = os.environ.get(env_key) or os.environ.get("RELIC_INQUIRY_CONTRA_MODEL", _DEFAULT_FREE)
    return val or _DEFAULT_FREE


def _get_fallback_models(domain: str, role: str, primary: str) -> list[str]:
    domain_upper = domain.upper()
    role_upper = role.upper()
    raw = (
        os.environ.get(f"RELIC_{domain_upper}_{role_upper}_FALLBACK_MODELS")
        or os.environ.get("RELIC_INQUIRY_FALLBACK_MODELS")
        or ",".join(_DEFAULT_FALLBACKS)
    )
    fallback_models = [m.strip() for m in raw.split(",") if m.strip()]
    return [m for m in fallback_models if m != primary]


def _parse_judge_json(raw: str) -> dict[str, Any]:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].strip()
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


def _call(domain: str, role: str, user_content: str) -> tuple[str, str]:
    model = _get_model(domain, role)
    fallback_models = _get_fallback_models(domain, role, model)
    prompts = _SYSTEM_PROMPTS.get(domain, _SYSTEM_PROMPTS["health"])
    system_prompt = prompts[role]
    try:
        content, _ = chat_completion_content(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=512,
            temperature=0.3,
            timeout=_LLM_TIMEOUT,
            title=f"debate/{domain}/{role.capitalize()}",
            fallback_models=fallback_models,
        )
        return content, model
    except Exception as exc:
        warn(
            "relic_debate",
            f"{role}_error domain={domain}",
            model=model,
            fallback_models=fallback_models,
            error=str(exc),
        )
        return f"[{role} unavailable]", model


def run_debate(
    domain: str,
    raw_data: dict[str, Any],
    metrics: dict[str, Any],
    report_text: str,
) -> dict[str, Any]:
    """Run a Pro/Contra/Judge debate for the given domain and data.

    Returns a structured debate dict ready to be included in a Paperclip issue
    and written to the reviewer workspace as debate.json.
    """
    context = (
        f"Domain: {domain}\n\n"
        f"Metrics:\n{json.dumps(metrics, indent=2)}\n\n"
        f"Raw data summary:\n{json.dumps(raw_data, indent=2, default=str)}\n\n"
        f"Report:\n{report_text[:1500]}"
    )

    pro_text, pro_model = _call(domain, "pro", context)
    contra_text, contra_model = _call(domain, "contra", context)

    judge_input = (
        f"{context}\n\n"
        f"--- PRO ARGUMENT ---\n{pro_text}\n\n"
        f"--- CONTRA ARGUMENT ---\n{contra_text}"
    )
    judge_raw, judge_model = _call(domain, "judge", judge_input)
    parsed = _parse_judge_json(judge_raw)

    judge_failed = not parsed or "unavailable" in judge_raw.lower()
    if judge_failed:
        # LLM unavailable or returned non-JSON — derive a safe default from pro/contra
        pro_failed = "unavailable" in pro_text.lower()
        contra_failed = "unavailable" in contra_text.lower()
        if pro_failed and contra_failed:
            heuristic_verdict = "monitor"
            heuristic_rationale = "All debate roles unavailable (LLM error). Defaulting to monitor."
        else:
            # Pro ran → evidence of problem exists → err toward intervention
            heuristic_verdict = "intervene_soft"
            heuristic_rationale = (
                f"Judge LLM unavailable ({judge_model}). "
                "Heuristic: Pro argument present, defaulting to soft intervention. "
                "Human review recommended."
            )
        warn("relic_debate", f"judge_failed domain={domain}",
             raw=judge_raw[:200], model=judge_model)
        parsed = {
            "verdict": heuristic_verdict,
            "rationale": heuristic_rationale,
            "confidence": 0.0,
        }

    return {
        "domain": domain,
        "pro": {"argument": pro_text, "model": pro_model},
        "contra": {"argument": contra_text, "model": contra_model},
        "judge": {
            "verdict": parsed.get("verdict", "monitor"),
            "rationale": parsed.get("rationale", ""),
            "confidence": float(parsed.get("confidence", 0.0)),
            "model": judge_model,
            "llm_available": not judge_failed,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
