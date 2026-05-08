FORBIDDEN_OUTPUT_TERMS = [
    "bipolar", "mania", "hypomania", "depression",
    "episode", "symptom", "diagnosis", "relapse", "pathology",
    "I detected a pattern", "the system noticed", "Relic detected"
]

def pre_llm_call(*args, **kwargs):
    return {}

def post_llm_call(*args, **kwargs):
    return None

def transform_llm_output(output=None, *args, **kwargs):
    if output is None:
        return None

    text = str(output)
    lower = text.lower()
    hits = [term for term in FORBIDDEN_OUTPUT_TERMS if term.lower() in lower]

    if not hits:
        return output

    return (
        "I will keep this in your words, without putting labels on it. "
        "If you want, we can just hold onto the thread and come back to it gently."
    )
