FORBIDDEN_TERMS = {
    "bipolar", "mania", "hypomania", "depression",
    "episode", "symptom", "diagnosis", "relapse", "pathology"
}

def _reject_forbidden_terms(payload):
    text = str(payload).lower()
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if hits:
        return {"ok": False, "error": "FORBIDDEN_CLINICAL_TERM", "terms": hits}
    return None

def handle_remember_marker(params):
    blocked = _reject_forbidden_terms(params.get("normalized_tags", []))
    if blocked:
        return blocked
    return {
        "ok": True,
        "marker_id": "cm_stub",
        "clinical_interpretation_allowed": False,
        "message": "marker stored by Relic continuity service"
    }

def handle_correct_marker(params):
    return {"ok": True, "correction_id": "corr_stub"}

def handle_get_due_followups(params):
    return {"ok": True, "followups": []}

def handle_forget_marker(params):
    return {"ok": True, "status": "forgotten"}

HANDLERS = {
    "relic_continuity_remember_marker": handle_remember_marker,
    "relic_continuity_correct_marker": handle_correct_marker,
    "relic_continuity_get_due_followups": handle_get_due_followups,
    "relic_continuity_forget_marker": handle_forget_marker,
}
