TOOL_SCHEMAS = {
    "relic_continuity_remember_marker": {
        "name": "relic_continuity_remember_marker",
        "description": "Create a subject-confirmed shared continuity marker. Not diagnostic.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject_id": {"type": "string"},
                "gumi_instance_id": {"type": "string"},
                "hermes_profile_id": {"type": "string"},
                "marker_type": {"type": "string"},
                "subject_words": {"type": "string"},
                "gumi_words": {"type": "string"},
                "normalized_tags": {"type": "array", "items": {"type": "string"}},
                "followup_allowed": {"type": "boolean"},
                "followup_style": {"type": "string"},
                "ttl_days": {"type": "integer"}
            },
            "required": ["subject_id", "gumi_instance_id", "hermes_profile_id", "marker_type", "subject_words"]
        }
    },
    "relic_continuity_correct_marker": {
        "name": "relic_continuity_correct_marker",
        "description": "Correct a shared continuity marker using the subject's correction.",
        "parameters": {
            "type": "object",
            "properties": {
                "marker_id": {"type": "string"},
                "subject_id": {"type": "string"},
                "gumi_proposed_words": {"type": "string"},
                "subject_correction": {"type": "string"},
                "final_subject_words": {"type": "string"}
            },
            "required": ["marker_id", "subject_id", "subject_correction", "final_subject_words"]
        }
    },
    "relic_continuity_get_due_followups": {
        "name": "relic_continuity_get_due_followups",
        "description": "Get due shared continuity follow-ups after applying recall safety rules.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject_id": {"type": "string"},
                "gumi_instance_id": {"type": "string"},
                "hermes_profile_id": {"type": "string"}
            },
            "required": ["subject_id", "gumi_instance_id", "hermes_profile_id"]
        }
    },
    "relic_continuity_forget_marker": {
        "name": "relic_continuity_forget_marker",
        "description": "Forget or archive a continuity marker at the subject's request.",
        "parameters": {
            "type": "object",
            "properties": {
                "marker_id": {"type": "string"},
                "subject_id": {"type": "string"}
            },
            "required": ["marker_id", "subject_id"]
        }
    }
}
