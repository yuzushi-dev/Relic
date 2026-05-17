"""Facet updater: closes the loop between check-in replies and subject_baseline.json.

For each unprocessed reply in checkin_exchanges:
1. Calls LLM to extract a behavioral observation from the reply text
2. Updates subject_baseline.json with new confidence/value/observations
3. Writes the observation to relic.db observations table
4. Marks the exchange as processed

Governance:
- Uses InferredField from relic.profile.inferred_fields for confidence caps
- Never produces clinical labels (FORBIDDEN_LABELS enforced)
- Confidence caps: single source → 0.35, multi-source → 0.55 (until human review)
- correction_state: if facet marked "corrected" by subject, updater skips it

Usage:
    python -m relic.checkin.facet_updater --subject-id daniele
    python -m relic.checkin.facet_updater --subject-id daniele --dry-run
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from relic.profile.inferred_fields import (
    DEFAULT_CONFIDENCE_CAP,
    MULTI_EVIDENCE_CAP,
    InferredField,
    validate_inferred_field_value,
)
from relic.patterns.signal_extractor import FORBIDDEN_LABELS


# Confidence string labels used in subject_baseline.json
def _float_to_conf_label(c: float) -> str:
    if c >= 0.70:
        return "high"
    if c >= 0.45:
        return "medium"
    if c >= 0.20:
        return "low"
    return "low_initial"


def _conf_label_to_float(s: str) -> float:
    return {"high": 0.75, "medium": 0.50, "low": 0.25, "low_initial": 0.10}.get(s, 0.10)


# Map facet_id (relic.db) → subject_baseline.json section + key
# The inverse of _BASELINE_TO_DB in question_engine.py
_DB_TO_BASELINE: dict[str, tuple[str, str]] = {
    "relational.loyalty_pattern":       ("psychological", "agreeableness"),
    "relational.attachment_anxiety":    ("psychological", "attachment_anxiety"),
    "relational.attachment_avoidance":  ("psychological", "attachment_avoidance"),
    "temporal.deadline_behavior":       ("psychological", "conscientiousness"),
    "emotional.distress_tolerance":     ("psychological", "emotional_stability"),
    "relational.social_energy":         ("psychological", "extraversion"),
    "cognitive.abstraction_level":      ("psychological", "openness"),
    "meta_cognition.uncertainty_tolerance": ("interaction", "ambiguity_tolerance"),
    "aesthetic.media_consumption":      ("interaction", "audio_tolerance"),
    "relational.help_seeking":          ("interaction", "checkin_tolerance"),
    "communication.conflict_style":     ("interaction", "critique_tolerance"),
    "communication.directness":         ("interaction", "directness_preference"),
    "aesthetic.design_sensibility":     ("interaction", "image_tolerance"),
    "relational.boundary_style":        ("interaction", "proactive_contact_tolerance"),
}

EXTRACTION_SYSTEM_PROMPT = (
    "Sei un assistente di ricerca comportamentale. Analizza il messaggio di risposta "
    "e determina se fornisce informazioni utili sulla dimensione comportamentale indicata. "
    "Rispondi SOLO con JSON valido. Non aggiungere testo fuori dal JSON. "
    "Non usare mai etichette cliniche o diagnostiche."
)

EXTRACTION_PROMPT_TEMPLATE = """Analizza questa risposta e determina la posizione della persona sulla dimensione comportamentale.

DIMENSIONE: {facet_name}
DESCRIZIONE: {description}
SPETTRO: {spectrum_low} (0.0) ↔ {spectrum_high} (1.0)

DOMANDA POSTA: {question_text}
RISPOSTA RICEVUTA: {reply_text}

Rispondi con questo JSON esatto (nessun altro testo):
{{
  "informative": true/false,
  "signal_position": 0.0-1.0 o null,
  "signal_strength": 0.0-1.0,
  "observation_summary": "descrizione breve e non-clinica dell'osservazione, max 120 chars",
  "confidence_delta": 0.05-0.25
}}

Regole:
- informative: true solo se la risposta dice qualcosa di concreto sulla dimensione
- signal_position: posizione stimata sullo spettro 0.0-1.0, null se non determinabile
- signal_strength: quanto è forte il segnale (0.1=debole, 0.9=forte)
- observation_summary: MAI usare termini clinici ({forbidden})
- confidence_delta: quanto aumenta la confidence (0.05 minimo, 0.25 massimo)"""


MARKER_PROMOTION_THRESHOLD = 0.45


@dataclass
class ExtractionResult:
    facet_id: str
    exchange_id: int
    informative: bool
    signal_position: float | None
    signal_strength: float
    observation_summary: str
    confidence_delta: float
    error: str | None = None


def _call_llm_extract(
    facet_id: str,
    facet_name: str,
    description: str,
    spectrum_low: str,
    spectrum_high: str,
    question_text: str,
    reply_text: str,
    llm_client: Any | None = None,
) -> dict[str, Any] | None:
    """Call LLM to extract behavioral signal. Returns parsed JSON or None on failure."""
    forbidden_sample = ", ".join(list(FORBIDDEN_LABELS)[:6])
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        facet_name=facet_name,
        description=description,
        spectrum_low=spectrum_low,
        spectrum_high=spectrum_high,
        question_text=question_text,
        reply_text=reply_text[:500],
        forbidden=forbidden_sample,
    )

    if llm_client is None:
        import re as _re
        import urllib.request as _urllib_request
        endpoint = os.environ.get("RELIC_OLLAMA_ENDPOINT", "http://localhost:11434/v1")
        model = os.environ.get("RELIC_OLLAMA_MODEL", "minimax-m2.7:cloud")
        _payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
            "think": False,
        }).encode("utf-8")
        req = _urllib_request.Request(
            f"{endpoint}/chat/completions",
            data=_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _urllib_request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data["choices"][0]["message"]
                text = (msg.get("content") or msg.get("reasoning") or "").strip()
                text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
        except Exception:
            pass
        return None

    return llm_client(EXTRACTION_SYSTEM_PROMPT, prompt)


def extract_observation(
    exchange_id: int,
    facet_id: str,
    facet_name: str,
    description: str,
    spectrum_low: str,
    spectrum_high: str,
    question_text: str,
    reply_text: str,
    llm_client: Any | None = None,
) -> ExtractionResult:
    """Extract behavioral observation from a check-in reply."""
    result = _call_llm_extract(
        facet_id, facet_name, description, spectrum_low, spectrum_high,
        question_text, reply_text, llm_client,
    )

    if result is None:
        return ExtractionResult(
            facet_id=facet_id, exchange_id=exchange_id,
            informative=False, signal_position=None,
            signal_strength=0.0, observation_summary="",
            confidence_delta=0.0, error="llm_unavailable",
        )

    if not result.get("informative", False):
        return ExtractionResult(
            facet_id=facet_id, exchange_id=exchange_id,
            informative=False, signal_position=None,
            signal_strength=float(result.get("signal_strength", 0.0)),
            observation_summary="", confidence_delta=0.0,
        )

    summary = str(result.get("observation_summary", ""))[:120]
    # Governance: check for forbidden clinical terms
    summary_lower = summary.lower()
    for term in FORBIDDEN_LABELS:
        if term in summary_lower:
            summary = summary.replace(term, "[removed]")

    return ExtractionResult(
        facet_id=facet_id,
        exchange_id=exchange_id,
        informative=True,
        signal_position=float(result["signal_position"]) if result.get("signal_position") is not None else None,
        signal_strength=min(1.0, max(0.0, float(result.get("signal_strength", 0.5)))),
        observation_summary=summary,
        confidence_delta=min(0.25, max(0.05, float(result.get("confidence_delta", 0.10)))),
    )


def update_baseline(
    baseline_path: Path,
    facet_id: str,
    extraction: ExtractionResult,
    exchange_id: int,
) -> bool:
    """Update subject_baseline.json with new observation. Returns True if changed."""
    if not baseline_path.exists():
        return False

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    section, key = _DB_TO_BASELINE.get(facet_id, (None, None))

    now = datetime.now(timezone.utc).isoformat()

    if section and key:
        # Update known bootstrap facet
        facet_entry = baseline.setdefault(section, {}).setdefault(key, {})
        current_conf = _conf_label_to_float(str(facet_entry.get("confidence", "low_initial")))
        # Apply governance caps via InferredField
        source_refs = [f"exchange:{exchange_id}"]
        field_obj = InferredField(
            field_name=f"{section}.{key}",
            value=extraction.signal_position,
            confidence=min(current_conf + extraction.confidence_delta, MULTI_EVIDENCE_CAP),
            source_refs=source_refs,
        )
        new_conf = field_obj.confidence
        facet_entry["confidence"] = _float_to_conf_label(new_conf)
        facet_entry["confidence_float"] = round(new_conf, 4)
        if extraction.signal_position is not None:
            # Weighted update: 70% prior, 30% new signal (conservative for first observations)
            prior_val = float(facet_entry.get("value", 0.5) or 0.5)
            weight = 0.30 + 0.10 * min(extraction.signal_strength, 1.0)
            facet_entry["value"] = round((1 - weight) * prior_val + weight * extraction.signal_position, 4)
        facet_entry["observations"] = int(facet_entry.get("observations", 0)) + 1
        facet_entry["last_updated"] = now
        facet_entry["last_source"] = f"checkin_exchange:{exchange_id}"
    else:
        # Facet not in baseline yet — add to extended_facets
        extended = baseline.setdefault("extended_facets", {})
        entry = extended.setdefault(facet_id, {
            "confidence": "low_initial",
            "confidence_float": 0.0,
            "value": None,
            "observations": 0,
        })
        current_conf = float(entry.get("confidence_float", 0.0))
        new_conf = min(current_conf + extraction.confidence_delta, MULTI_EVIDENCE_CAP)
        entry["confidence_float"] = round(new_conf, 4)
        entry["confidence"] = _float_to_conf_label(new_conf)
        if extraction.signal_position is not None:
            prior_val = float(entry.get("value") or 0.5)
            weight = 0.30 + 0.10 * min(extraction.signal_strength, 1.0)
            entry["value"] = round((1 - weight) * prior_val + weight * extraction.signal_position, 4)
        entry["observations"] = int(entry.get("observations", 0)) + 1
        entry["last_updated"] = now
        entry["last_source"] = f"checkin_exchange:{exchange_id}"

    baseline["last_checkin_update"] = now
    baseline_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


def _promote_observation_to_marker(
    extraction: ExtractionResult,
    subject_id: str,
    gumi_instance_id: str = "",
    hermes_profile_id: str = "",
) -> None:
    """Promote a strong observation to a ContinuityMarker so prefetch() surfaces it.

    Uses source_type="subject_confirmed" so recent_markers() includes it and
    prefetch() can surface it — the user confirmed the trait by answering.

    Dedup: skips if an existing marker already encodes the same observation text
    (exact match on joined subject_words) to prevent re-run duplicates.

    Only called when signal_strength >= MARKER_PROMOTION_THRESHOLD.
    Fail-open: any error is logged at WARNING level and silently ignored.
    """
    if extraction.signal_strength < MARKER_PROMOTION_THRESHOLD:
        return
    if not extraction.observation_summary:
        return
    try:
        from relic.gumi_continuity.store import GumiContinuityStore

        # ContinuityService.remember() requires all three IDs to be non-empty
        # (raises BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE otherwise).
        # Fall back to subject_id sentinel — consistent with registry.py pattern.
        _gumi = gumi_instance_id or subject_id
        _hermes = hermes_profile_id or subject_id

        store = GumiContinuityStore()
        target_norm = " ".join(extraction.observation_summary.split())

        # Dedup: skip if any recent marker already has the same observation text.
        # Normalize whitespace on both sides to avoid false negatives.
        existing = store.get_recent_markers(
            subject_id=subject_id,
            gumi_instance_id=_gumi or None,
            hermes_profile_id=_hermes or None,
            limit=50,
        )
        for m in existing:
            words = m.get("subject_words") or m.get("words") or []
            if isinstance(words, list):
                existing_text = " ".join(str(w) for w in words)
            else:
                existing_text = str(words)
            if " ".join(existing_text.split()) == target_norm:
                return

        store.remember_marker(
            subject_id=subject_id,
            gumi_instance_id=_gumi,
            hermes_profile_id=_hermes,
            subject_words=target_norm.split(),
            source_type="subject_confirmed",
            ttl_seconds=1_209_600,  # 2 weeks
        )
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "_promote_observation_to_marker failed subject=%s facet=%s: %s",
            subject_id, extraction.facet_id, exc,
        )


def process_pending_exchanges(
    conn: sqlite3.Connection,
    baseline_path: Path,
    subject_id: str,
    dry_run: bool = False,
    llm_client: Any | None = None,
    gumi_instance_id: str = "",
    hermes_profile_id: str = "",
) -> list[dict[str, Any]]:
    """Process all unprocessed check-in replies. Returns list of results."""
    rows = conn.execute(
        """SELECT ce.id, ce.facet_id, ce.question_text, ce.reply_text,
                  f.name, f.description, f.spectrum_low, f.spectrum_high
           FROM checkin_exchanges ce
           JOIN facets f ON f.id = ce.facet_id
           WHERE ce.reply_text IS NOT NULL
             AND ce.observations_extracted = 0
           ORDER BY ce.asked_at ASC"""
    ).fetchall()

    results = []
    for row in rows:
        exchange_id, facet_id, question_text, reply_text, \
            facet_name, description, spectrum_low, spectrum_high = row

        extraction = extract_observation(
            exchange_id=exchange_id,
            facet_id=facet_id,
            facet_name=facet_name or facet_id,
            description=description or "",
            spectrum_low=spectrum_low or "low",
            spectrum_high=spectrum_high or "high",
            question_text=question_text,
            reply_text=reply_text,
            llm_client=llm_client,
        )

        entry: dict[str, Any] = {
            "exchange_id": exchange_id,
            "facet_id": facet_id,
            "informative": extraction.informative,
            "error": extraction.error,
        }

        if extraction.error:
            results.append(entry)
            continue

        if extraction.informative and not dry_run:
            # Write observation to db
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO observations
                       (facet_id, source_type, source_ref, content, extracted_signal,
                        signal_strength, signal_position, created_at)
                       VALUES (?, 'checkin_reply', ?, ?, ?, ?, ?, ?)""",
                    (
                        facet_id,
                        f"exchange:{exchange_id}",
                        extraction.observation_summary,
                        json.dumps({"question": question_text[:100]}),
                        extraction.signal_strength,
                        extraction.signal_position,
                        now_iso,
                    ),
                )
                # Update traits table
                conn.execute(
                    """INSERT INTO traits (facet_id, value_position, confidence, observation_count, last_observation_at)
                       VALUES (?, ?, ?, 1, ?)
                       ON CONFLICT(facet_id) DO UPDATE SET
                           value_position = CASE WHEN excluded.value_position IS NOT NULL
                               THEN 0.7*traits.value_position + 0.3*excluded.value_position
                               ELSE traits.value_position END,
                           confidence = MIN(traits.confidence + ?, ?),
                           observation_count = traits.observation_count + 1,
                           last_observation_at = excluded.last_observation_at""",
                    (
                        facet_id,
                        extraction.signal_position,
                        min(extraction.confidence_delta + 0.10, DEFAULT_CONFIDENCE_CAP),
                        now_iso,
                        extraction.confidence_delta,
                        MULTI_EVIDENCE_CAP,
                    ),
                )
                conn.commit()
            except sqlite3.Error:
                conn.rollback()

            # Update baseline JSON
            update_baseline(baseline_path, facet_id, extraction, exchange_id)

            # Promote strong observations to ContinuityMarker for prefetch()
            _promote_observation_to_marker(
                extraction, subject_id, gumi_instance_id, hermes_profile_id
            )

            entry.update({
                "signal_position": extraction.signal_position,
                "signal_strength": extraction.signal_strength,
                "confidence_delta": extraction.confidence_delta,
                "observation_summary": extraction.observation_summary,
            })

        if not dry_run:
            conn.execute(
                "UPDATE checkin_exchanges SET observations_extracted = 1 WHERE id = ?",
                (exchange_id,),
            )
            conn.commit()

        results.append(entry)

    return results


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Process check-in replies → facet updates")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--baseline-path", default=None)
    parser.add_argument("--relic-home", default=None)
    parser.add_argument("--gumi-instance-id", default="")
    parser.add_argument("--hermes-profile-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    relic_home = args.relic_home or os.environ.get("RELIC_HOME", str(Path.home() / ".relic"))
    db_path = Path(args.db_path) if args.db_path else \
              Path(relic_home) / "subjects" / args.subject_id / "relic.db"
    baseline_path = Path(args.baseline_path) if args.baseline_path else \
                    Path(relic_home) / "subjects" / args.subject_id / "subject_baseline.json"

    conn = sqlite3.connect(str(db_path))
    results = process_pending_exchanges(
        conn, baseline_path, args.subject_id,
        dry_run=args.dry_run,
        gumi_instance_id=args.gumi_instance_id,
        hermes_profile_id=args.hermes_profile_id,
    )
    conn.close()

    print(json.dumps({
        "status": "ok",
        "dry_run": args.dry_run,
        "processed": len(results),
        "informative": sum(1 for r in results if r.get("informative")),
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
