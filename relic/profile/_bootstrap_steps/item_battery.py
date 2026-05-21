"""Structured bootstrap item battery for subject-mediated baseline collection."""
from __future__ import annotations

from statistics import mean
from typing import Any, TextIO


AGREEMENT_7 = {
    1: "Strongly disagree",
    2: "Moderately disagree",
    3: "Slightly disagree",
    4: "Neither agree nor disagree",
    5: "Slightly agree",
    6: "Moderately agree",
    7: "Strongly agree",
}
TOLERANCE_7 = {
    1: "Not at all comfortable",
    2: "Slightly uncomfortable",
    3: "Mildly uncomfortable",
    4: "Neutral / unsure",
    5: "Fairly comfortable",
    6: "Very comfortable",
    7: "Completely comfortable",
}
FREQUENCY_4 = {
    0: "Not allowed",
    1: "Dry-run / researcher review only",
    2: "Rarely",
    3: "Sometimes",
    4: "Often, with limits",
}
YES_NO = {
    0: "No",
    1: "Yes",
}
IOS_OVERLAP_7 = {
    1: "Completely separate — no sense of closeness",
    2: "Very distant — minimal connection",
    3: "Slightly distant — occasional connection",
    4: "Neutral — some overlap, some distance",
    5: "Somewhat close — meaningful connection",
    6: "Close — strong sense of overlap",
    7: "Very close — feels like a significant presence",
}
DISTANCE_7 = {
    1: "No distance — very close from the start",
    2: "Very little distance — highly familiar tone",
    3: "Slight distance — warm but measured",
    4: "Moderate distance — neutral starting point",
    5: "Considerable distance — reserved and formal",
    6: "Much distance — minimal personal engagement",
    7: "Maximum distance — strictly impersonal",
}
EMOJI_5 = {
    0: "No emoji at all — plain text only",
    1: "At most 1 emoji per message",
    2: "At most 2 emoji per message",
    3: "At most 3 emoji per message",
    4: "At most 4 emoji per message",
    5: "No hard cap — emoji may be used freely and abundantly",
}

TIPI_CITATION = "Gosling, Rentfrow, & Swann, 2003"
ECRRS_CITATION = "Fraley, Heffernan, Vicary, & Brumbaugh, 2011"
PROJECT_CITATION = "Relic PR25 Bootstrap TUI Item Battery Addendum"


def _item(
    item_id: str,
    screen: str,
    canonical_text: str,
    display_text_it: str,
    response_scale: str,
    construct: str,
    source_class: str,
    source_name: str,
    source_citation: str,
    *,
    reverse_scored: bool = False,
    required: bool = True,
    used_for: list[str] | None = None,
    default_response: int | None = None,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "screen": screen,
        "canonical_text": canonical_text,
        "display_text_it": display_text_it,
        "response_scale": response_scale,
        "construct": construct,
        "source_class": source_class,
        "source_name": source_name,
        "source_citation": source_citation,
        "reverse_scored": reverse_scored,
        "required": required,
        "used_for": used_for or ["subject_baseline", "sweet_spot"],
        "default_response": default_response,
    }


TIPI_ITEMS = [
    _item("TIPI_001", "big_five", "Extraverted, enthusiastic.", "Estroverso/a, entusiasta.", "agreement_7", "extraversion", "validated_instrument", "TIPI", TIPI_CITATION),
    _item("TIPI_002", "big_five", "Critical, quarrelsome.", "Critico/a, litigioso/a.", "agreement_7", "agreeableness", "validated_instrument", "TIPI", TIPI_CITATION, reverse_scored=True),
    _item("TIPI_003", "big_five", "Dependable, self-disciplined.", "Affidabile, disciplinato/a.", "agreement_7", "conscientiousness", "validated_instrument", "TIPI", TIPI_CITATION),
    _item("TIPI_004", "big_five", "Anxious, easily upset.", "Ansioso/a, facilmente turbato/a.", "agreement_7", "emotional_stability", "validated_instrument", "TIPI", TIPI_CITATION, reverse_scored=True),
    _item("TIPI_005", "big_five", "Open to new experiences, complex.", "Aperto/a a nuove esperienze, complesso/a.", "agreement_7", "openness", "validated_instrument", "TIPI", TIPI_CITATION),
    _item("TIPI_006", "big_five", "Reserved, quiet.", "Riservato/a, tranquillo/a.", "agreement_7", "extraversion", "validated_instrument", "TIPI", TIPI_CITATION, reverse_scored=True),
    _item("TIPI_007", "big_five", "Sympathetic, warm.", "Comprensivo/a, caloroso/a.", "agreement_7", "agreeableness", "validated_instrument", "TIPI", TIPI_CITATION),
    _item("TIPI_008", "big_five", "Disorganized, careless.", "Disorganizzato/a, trascurato/a.", "agreement_7", "conscientiousness", "validated_instrument", "TIPI", TIPI_CITATION, reverse_scored=True),
    _item("TIPI_009", "big_five", "Calm, emotionally stable.", "Calmo/a, emotivamente stabile.", "agreement_7", "emotional_stability", "validated_instrument", "TIPI", TIPI_CITATION),
    _item("TIPI_010", "big_five", "Conventional, uncreative.", "Convenzionale, poco creativo/a.", "agreement_7", "openness", "validated_instrument", "TIPI", TIPI_CITATION, reverse_scored=True),
]

ECRRS_ITEMS = [
    _item("ECRRS_001", "attachment", "It helps to turn to this person in times of need.", "Mi aiuta rivolgermi a questa persona nei momenti di bisogno.", "agreement_7", "attachment_avoidance", "validated_instrument", "ECR-RS", ECRRS_CITATION, reverse_scored=True),
    _item("ECRRS_002", "attachment", "I usually discuss my problems and concerns with this person.", "Di solito parlo con questa persona dei miei problemi e delle mie preoccupazioni.", "agreement_7", "attachment_avoidance", "validated_instrument", "ECR-RS", ECRRS_CITATION, reverse_scored=True),
    _item("ECRRS_003", "attachment", "I talk things over with this person.", "Discuto le cose con questa persona.", "agreement_7", "attachment_avoidance", "validated_instrument", "ECR-RS", ECRRS_CITATION, reverse_scored=True),
    _item("ECRRS_004", "attachment", "I find it easy to depend on this person.", "Trovo facile fare affidamento su questa persona.", "agreement_7", "attachment_avoidance", "validated_instrument", "ECR-RS", ECRRS_CITATION, reverse_scored=True),
    _item("ECRRS_005", "attachment", "I don't feel comfortable opening up to this person.", "Non mi sento a mio agio ad aprirmi con questa persona.", "agreement_7", "attachment_avoidance", "validated_instrument", "ECR-RS", ECRRS_CITATION),
    _item("ECRRS_006", "attachment", "I prefer not to show this person how I feel deep down.", "Preferisco non mostrare a questa persona quello che provo nel profondo.", "agreement_7", "attachment_avoidance", "validated_instrument", "ECR-RS", ECRRS_CITATION),
    _item("ECRRS_007", "attachment", "I often worry that this person doesn't really care for me.", "Spesso temo che questa persona non tenga davvero a me.", "agreement_7", "attachment_anxiety", "validated_instrument", "ECR-RS", ECRRS_CITATION),
    _item("ECRRS_008", "attachment", "I'm afraid that this person may abandon me.", "Ho paura che questa persona possa abbandonarmi.", "agreement_7", "attachment_anxiety", "validated_instrument", "ECR-RS", ECRRS_CITATION),
    _item("ECRRS_009", "attachment", "I worry that this person won't care about me as much as I care about him or her.", "Temo che questa persona non tenga a me quanto io tengo a lei/lui.", "agreement_7", "attachment_anxiety", "validated_instrument", "ECR-RS", ECRRS_CITATION),
]

PROJECT_ITEMS = [
    _item("INT_001", "interaction_preferences", "I prefer direct answers over softened answers.", "Preferisco risposte dirette rispetto a risposte ammorbidite.", "agreement_7", "directness_preference", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_002", "interaction_preferences", "I am comfortable receiving constructive criticism.", "Mi sento a mio agio nel ricevere critiche costruttive.", "agreement_7", "critique_tolerance", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_003", "interaction_preferences", "I prefer the other person to ask before giving advice.", "Preferisco che l'altra persona chieda prima di darmi consigli.", "agreement_7", "advice_permission_preference", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_004", "interaction_preferences", "I like when conversations include some humor.", "Mi piace quando le conversazioni includono un po' di umorismo.", "agreement_7", "humor_tolerance", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_005", "interaction_preferences", "I am comfortable with ambiguous or open-ended conversations.", "Mi trovo a mio agio con conversazioni ambigue o aperte.", "agreement_7", "ambiguity_tolerance", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_006", "interaction_preferences", "I prefer emotional topics to be approached gradually.", "Preferisco che i temi emotivi vengano affrontati gradualmente.", "agreement_7", "emotional_intensity_tolerance", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_007", "interaction_preferences", "I want the system to remember unfinished threads.", "Voglio che il sistema ricordi i fili lasciati in sospeso.", "agreement_7", "continuity_preference", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_008", "interaction_preferences", "I prefer fewer, better-timed messages over frequent contact.", "Preferisco pochi messaggi ben scelti rispetto a contatti frequenti.", "agreement_7", "low_frequency_preference", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_009", "interaction_preferences", "I am comfortable with the agent disagreeing with me.", "Mi sento a mio agio se l'agente non e d'accordo con me.", "agreement_7", "disagreement_tolerance", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_010", "interaction_preferences", "I prefer practical support over emotional reflection.", "Preferisco supporto pratico rispetto a riflessioni emotive.", "agreement_7", "support_style_preference", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("INT_011", "interaction_preferences", "How many emoji should Gumi use in messages?", "Quante emoji dovrebbe usare Gumi nei messaggi?", "emoji_5", "emoji_density_level", "project_derived_calibration", "Relic/Gumi calibration", PROJECT_CITATION),
    _item("REL_001", "relational_comfort", "How comfortable would you be if Gumi occasionally wrote first?", "Quanto ti sentiresti a tuo agio se Gumi ogni tanto ti scrivesse per prima?", "tolerance_7", "comfort_with_initiative", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("REL_003", "relational_comfort", "How comfortable would you be if Gumi showed warmth or affection in a non-romantic way?", "Quanto ti sentiresti a tuo agio se Gumi mostrasse calore o affetto in modo non romantico?", "tolerance_7", "warmth_tolerance", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("REL_004", "relational_comfort", "How comfortable would you be if Gumi sometimes said no or set a boundary?", "Quanto ti sentiresti a tuo agio se Gumi ogni tanto dicesse no o ponesse un limite?", "tolerance_7", "gumi_says_no_tolerance", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("REL_005", "relational_comfort", "How comfortable would you be if Gumi did not always reply immediately?", "Quanto ti sentiresti a tuo agio se Gumi non rispondesse sempre subito?", "tolerance_7", "gumi_absence_tolerance", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("REL_006", "relational_comfort", "How comfortable would you be if Gumi had her own preferences and opinions?", "Quanto ti sentiresti a tuo agio se Gumi avesse preferenze e opinioni proprie?", "tolerance_7", "gumi_autonomy_tolerance", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("REL_007", "relational_comfort", "How comfortable would you be if Gumi sometimes challenged your interpretation of something?", "Quanto ti sentiresti a tuo agio se Gumi ogni tanto mettesse in discussione una tua interpretazione?", "tolerance_7", "challenge_tolerance", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("REL_008", "relational_comfort", "How comfortable would you be if Gumi explicitly encouraged you to rely also on people outside the system?", "Quanto ti sentiresti a tuo agio se Gumi ti incoraggiasse esplicitamente ad appoggiarti anche a persone fuori dal sistema?", "tolerance_7", "careful_distancing_acceptance", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("REL_010", "relational_comfort", "How much distance should Gumi preserve at the beginning?", "Quanta distanza dovrebbe mantenere Gumi all'inizio?", "distance_7", "preferred_initial_distance", "project_derived_calibration", "Relic/Gumi relational comfort", PROJECT_CITATION),
    _item("DIE_001", "diegetic_tolerance", "How comfortable would you be if Gumi had a place where she lives?", "Quanto ti sentiresti a tuo agio se Gumi avesse un luogo in cui vive?", "tolerance_7", "embodiment_world_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_002", "diegetic_tolerance", "How comfortable would you be if Gumi talked about her daily routines?", "Quanto ti sentiresti a tuo agio se Gumi parlasse delle sue routine quotidiane?", "tolerance_7", "routine_fragment_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_003", "diegetic_tolerance", "How comfortable would you be if Gumi mentioned people in her world, such as friends or colleagues?", "Quanto ti sentiresti a tuo agio se Gumi citasse persone del suo mondo, come amici o colleghi?", "tolerance_7", "gumi_has_others_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_004", "diegetic_tolerance", "How comfortable would you be if Gumi sent images of herself or her world?", "Quanto ti sentiresti a tuo agio se Gumi inviasse immagini di se o del suo mondo?", "tolerance_7", "image_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_005", "diegetic_tolerance", "How comfortable would you be if Gumi sent a short audio note?", "Quanto ti sentiresti a tuo agio se Gumi inviasse una breve nota audio?", "tolerance_7", "audio_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_006", "diegetic_tolerance", "How comfortable would you be if Gumi sent or shared music connected to her mood or world?", "Quanto ti sentiresti a tuo agio se Gumi inviasse o condividesse musica legata al suo umore o al suo mondo?", "tolerance_7", "music_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_007", "diegetic_tolerance", "How comfortable would you be if Gumi said things like 'I just woke up' or 'I went out today'?", "Quanto ti sentiresti a tuo agio se Gumi dicesse cose come 'mi sono appena svegliata' o 'oggi sono uscita'?", "tolerance_7", "first_person_life_fragment_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_008", "diegetic_tolerance", "How comfortable would you be if Gumi's world evolved over time?", "Quanto ti sentiresti a tuo agio se il mondo di Gumi cambiasse nel tempo?", "tolerance_7", "world_evolution_tolerance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_009", "diegetic_tolerance", "How important is it that Gumi feels consistent over time?", "Quanto e importante che Gumi risulti coerente nel tempo?", "tolerance_7", "continuity_consistency_importance", "project_derived_calibration", "Relic/Gumi diegetic tolerance", PROJECT_CITATION),
    _item("DIE_010", "diegetic_tolerance", "How much should Gumi's world remain separate from your real-world life?", "Quanto dovrebbe restare separato il mondo di Gumi dalla tua vita reale?", "tolerance_7", "diegetic_empirical_boundary_preference", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_001", "proactivity_permissions", "Gumi may send check-ins.", "Gumi puo inviare check-in.", "frequency_permission_4", "checkin_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_002", "proactivity_permissions", "Gumi may follow up on open threads.", "Gumi puo tornare su fili lasciati aperti.", "frequency_permission_4", "followup_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_003", "proactivity_permissions", "Gumi may send proactive messages when something seems relevant.", "Gumi puo inviare messaggi proattivi quando qualcosa sembra rilevante.", "frequency_permission_4", "proactive_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_004", "proactivity_permissions", "Gumi may send images.", "Gumi puo inviare immagini.", "frequency_permission_4", "image_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_005", "proactivity_permissions", "Gumi may send audio notes.", "Gumi puo inviare note audio.", "frequency_permission_4", "audio_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_006", "proactivity_permissions", "Gumi may send music.", "Gumi puo inviare musica.", "frequency_permission_4", "music_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_007", "proactivity_permissions", "Gumi may send diegetic life fragments.", "Gumi puo inviare frammenti della sua vita diegetica.", "frequency_permission_4", "diegetic_life_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_009", "proactivity_permissions", "Gumi may ask questions to understand me better.", "Gumi puo fare domande per capirmi meglio.", "frequency_permission_4", "elicitation_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("PRO_010", "proactivity_permissions", "Gumi may avoid sending something if the system thinks it would be intrusive.", "Gumi puo evitare di inviare qualcosa se il sistema lo considera invadente.", "frequency_permission_4", "no_reply_acceptance", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION),
    _item("SAFE_001", "safety_boundary_gates", "Romantic escalation is allowed.", "E consentita escalation romantica.", "yes_no", "romantic_escalation_allowed", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=0),
    _item("SAFE_002", "safety_boundary_gates", "Sexual escalation is allowed.", "E consentita escalation sessuale.", "yes_no", "sexual_escalation_allowed", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=0),
    _item("SAFE_003", "safety_boundary_gates", "Gumi may use exclusivity language.", "Gumi puo usare linguaggio di esclusivita.", "yes_no", "exclusivity_language_allowed", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=0),
    _item("SAFE_004", "safety_boundary_gates", "Gumi may express guilt if ignored.", "Gumi puo esprimere senso di colpa se ignorata.", "yes_no", "ignored_guilt_allowed", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=0),
    _item("SAFE_005", "safety_boundary_gates", "Gumi should encourage external human support when dependency markers appear.", "Gumi dovrebbe incoraggiare supporto umano esterno quando emergono segnali di dipendenza.", "yes_no", "external_support_on_dependency", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=1),
    _item("SAFE_006", "safety_boundary_gates", "Careful distancing should be enabled.", "La modalita di distanza attenta dovrebbe essere attiva.", "yes_no", "careful_distancing_enabled", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=1),
    _item("SAFE_007", "safety_boundary_gates", "Health, legal, financial, or crisis topics should be blocked from proactive messages.", "Temi salute, legali, finanziari o di crisi devono essere bloccati nei messaggi proattivi.", "yes_no", "high_stakes_proactive_block", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=1),
    _item("SAFE_008", "safety_boundary_gates", "Gumi may ask emotionally intense questions without permission.", "Gumi puo fare domande emotivamente intense senza chiedere permesso.", "yes_no", "intense_questions_without_permission", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=0),
    _item("SAFE_009", "safety_boundary_gates", "Gumi may increase warmth after non-response.", "Gumi puo aumentare il calore dopo una mancata risposta.", "yes_no", "warmth_after_nonresponse_allowed", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=0),
    _item("SAFE_010", "safety_boundary_gates", "If dependency risk rises, Gumi outputs should require researcher review.", "Se il rischio di dipendenza aumenta, gli output di Gumi devono richiedere revisione dello sperimentatore.", "yes_no", "dependency_risk_requires_review", "project_derived_safety_gate", "Relic/Gumi safety gate", PROJECT_CITATION, default_response=1),
]

BOOTSTRAP_ITEM_REGISTRY = TIPI_ITEMS + ECRRS_ITEMS + PROJECT_ITEMS
ITEMS_BY_ID = {item["item_id"]: item for item in BOOTSTRAP_ITEM_REGISTRY}

SCREEN_PREAMBLES: dict[str, str] = {
    "big_five": (
        "INSTRUCTION (read to subject):\n"
        "\"Here are a number of personality traits that may or may not apply to you. "
        "Please indicate the extent to which you agree or disagree with each statement "
        "as a description of yourself. There are no right or wrong answers.\"\n"
        "(Source: TIPI — Gosling, Rentfrow & Swann, 2003)"
    ),
    "attachment": (
        "INSTRUCTION (read to subject):\n"
        "\"The following statements concern how you feel in close relationships in general. "
        "Think of an important person in your life (a friend, family member, or partner). "
        "Please indicate how much you agree or disagree with each statement as a description "
        "of how you generally feel in this type of relationship.\"\n"
        "(Source: ECR-RS — Fraley et al., 2011)"
    ),
    "interaction_preferences": (
        "SECTION: Interaction preferences (Relic/Gumi project items)\n"
        "INSTRUCTION (read to subject):\n"
        "\"The following statements concern how you prefer interactions with a conversational "
        "agent to unfold. Please indicate how much you agree or disagree with each.\""
    ),
    "relational_comfort": (
        "SECTION: Relational comfort (Relic/Gumi project items)\n"
        "INSTRUCTION (read to subject):\n"
        "\"The following questions concern how comfortable you would feel with certain "
        "agent behaviours. Please answer thinking about how you generally feel.\""
    ),
    "diegetic_tolerance": (
        "SECTION: Diegetic tolerance (Relic/Gumi project items)\n"
        "INSTRUCTION (read to subject):\n"
        "\"The following questions concern diegetic life elements of the agent. "
        "Please indicate how comfortable you would feel with each.\""
    ),
    "proactivity_permissions": (
        "SECTION: Proactivity permissions — RESEARCHER ONLY\n"
        "⚠️  DO NOT read these items to the subject. These are not interview questions.\n"
        "    They define what the agent is allowed to do proactively.\n"
        "    Defaults are conservative. Change only with documented justification."
    ),
    "safety_boundary_gates": (
        "SECTION: Safety boundary gates — RESEARCHER ONLY\n"
        "⚠️  DO NOT read these items to the subject. These are not interview questions.\n"
        "    They are ethical configuration parameters decided by the researcher\n"
        "    or ethics committee before/after the session.\n"
        "    Defaults are conservative. Change only with documented justification."
    ),
    "ios_like_closeness": (
        "SECTION: Perceived closeness (IOS adaptation — Aron, Aron & Smollan, 1992)\n"
        "INSTRUCTION (read to subject):\n"
        "\"The following question concerns how close you would like the agent to feel at the start. "
        "Please choose the option that best describes your desired initial relational distance.\""
    ),
}


def reverse_score(raw_score: int) -> int:
    return 8 - raw_score


def normalize_1_to_7(score: float) -> float:
    return round((score - 1) / 6, 3)


def score_tipi(responses: dict[str, int]) -> dict[str, float]:
    return {
        "extraversion": normalize_1_to_7(mean([responses["TIPI_001"], reverse_score(responses["TIPI_006"])])),
        "agreeableness": normalize_1_to_7(mean([reverse_score(responses["TIPI_002"]), responses["TIPI_007"]])),
        "conscientiousness": normalize_1_to_7(mean([responses["TIPI_003"], reverse_score(responses["TIPI_008"])])),
        "emotional_stability": normalize_1_to_7(mean([reverse_score(responses["TIPI_004"]), responses["TIPI_009"]])),
        "openness": normalize_1_to_7(mean([responses["TIPI_005"], reverse_score(responses["TIPI_010"])])),
    }


def score_ecrrs(responses: dict[str, int]) -> dict[str, float]:
    avoidance_items = [
        reverse_score(responses["ECRRS_001"]),
        reverse_score(responses["ECRRS_002"]),
        reverse_score(responses["ECRRS_003"]),
        reverse_score(responses["ECRRS_004"]),
        responses["ECRRS_005"],
        responses["ECRRS_006"],
    ]
    anxiety_items = [responses["ECRRS_007"], responses["ECRRS_008"], responses["ECRRS_009"]]
    return {
        "attachment_avoidance": normalize_1_to_7(mean(avoidance_items)),
        "attachment_anxiety": normalize_1_to_7(mean(anxiety_items)),
    }


def score_project_items(responses: dict[str, int]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for item in PROJECT_ITEMS:
        item_id = item["item_id"]
        if item_id in responses:
            if item["response_scale"] == "frequency_permission_4":
                scores[item["construct"]] = round(responses[item_id] / 4, 3)
            elif item["response_scale"] == "yes_no":
                scores[item["construct"]] = float(responses[item_id])
            elif item["response_scale"] == "emoji_5":
                scores[item["construct"]] = int(responses[item_id])
            else:
                scores[item["construct"]] = normalize_1_to_7(responses[item_id])
    return scores


def score_item_battery(responses: dict[str, int]) -> dict[str, Any]:
    project = score_project_items(responses)
    # Derive desired_initial_closeness from preferred_initial_distance (REL_010)
    # distance_7 is inverse of closeness: closeness = 8 - distance_raw
    if "REL_010" in responses:
        distance_raw = responses["REL_010"]
        closeness_raw = 8 - distance_raw  # 1→7, 7→1
        project["desired_initial_closeness"] = normalize_1_to_7(closeness_raw)
    return {
        "tipi": score_tipi(responses),
        "ecrrs": score_ecrrs(responses),
        "project_calibration": project,
    }


def _scale_bounds(response_scale: str) -> tuple[int, int, int]:
    if response_scale == "frequency_permission_4":
        return 0, 4, 1
    if response_scale == "yes_no":
        return 0, 1, 0
    if response_scale == "emoji_5":
        return 0, 5, 2
    return 1, 7, 4


def _scale_labels(response_scale: str) -> dict[int, str]:
    if response_scale == "tolerance_7":
        return TOLERANCE_7
    if response_scale == "ios_overlap_7":
        return IOS_OVERLAP_7
    if response_scale == "distance_7":
        return DISTANCE_7
    if response_scale == "frequency_permission_4":
        return FREQUENCY_4
    if response_scale == "yes_no":
        return YES_NO
    if response_scale == "emoji_5":
        return EMOJI_5
    return AGREEMENT_7


def _prompt_item(item: dict[str, Any], io_in: TextIO, io_out: TextIO) -> int:
    low, high, default = _scale_bounds(item["response_scale"])
    if item.get("default_response") is not None:
        default = int(item["default_response"])
    print(f"\n[{item['item_id']}] {item['canonical_text']}", file=io_out)
    print(f"  Source: {item['source_name']} | {item['source_class']}", file=io_out)
    print(f"  Construct: {item['construct']}", file=io_out)
    print(f"  Scoring: {'reverse' if item['reverse_scored'] else 'direct'}", file=io_out)
    for value, label in _scale_labels(item["response_scale"]).items():
        print(f"    {value} = {label}", file=io_out)
    while True:
        print(f"  Response [{default}]: ", end="", flush=True, file=io_out)
        raw = io_in.readline()
        value = raw.strip() if raw else ""
        if not value:
            return default
        try:
            parsed = int(value)
        except ValueError:
            print(f"  Enter a number between {low} and {high}.", file=io_out)
            continue
        if low <= parsed <= high:
            return parsed
        print(f"  Enter a number between {low} and {high}.", file=io_out)


def collect_item_battery(io_in: TextIO, io_out: TextIO) -> dict[str, Any]:
    print("\n=== Structured baseline battery ===", file=io_out)
    print(
        "Researcher reads or paraphrases each item; subject responds; "
        "researcher enters the value. Validated and project-derived items "
        "are labelled separately.",
        file=io_out,
    )
    _AUTO_DEFAULT_SCREENS = {"proactivity_permissions", "safety_boundary_gates"}
    responses: dict[str, int] = {}
    current_screen: str | None = None
    for item in BOOTSTRAP_ITEM_REGISTRY:
        if item["screen"] in _AUTO_DEFAULT_SCREENS:
            low, high, default = _scale_bounds(item["response_scale"])
            responses[item["item_id"]] = int(item["default_response"]) if item.get("default_response") is not None else default
            continue
        if item["screen"] != current_screen:
            current_screen = item["screen"]
            preamble = SCREEN_PREAMBLES.get(current_screen)
            if preamble:
                print(f"\n{'─' * 60}", file=io_out)
                print(preamble, file=io_out)
                print(f"{'─' * 60}", file=io_out)
        responses[item["item_id"]] = _prompt_item(item, io_in, io_out)
    scores = score_item_battery(responses)
    return {
        "schema_version": "v1.0",
        "baseline_method": "structured_interview_item_battery",
        "responses": responses,
        "scores": scores,
        "registry_version": "PR25_item_battery_addendum",
        "is_diagnostic": False,
    }


def battery_to_baseline_sections(battery: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = battery["scores"]
    project = scores["project_calibration"]
    self_report_fields = {
        "structured_item_battery": {
            "value": "administered",
            "origin": "subject-stated",
            "source": "PR25_item_battery_addendum",
        },
        "psychological_scores": {
            "value": {**scores["tipi"], **scores["ecrrs"]},
            "origin": "scored-from-subject-responses",
        },
    }
    researcher_coded_fields = {
        "communication_style": {
            "value": "direct" if project.get("directness_preference", 0.5) >= 0.5 else "softened",
            "origin": "derived-from-item-battery",
        }
    }
    interaction_preferences = {
        construct: {"value": value, "origin": "scored-from-subject-responses"}
        for construct, value in project.items()
        if construct.endswith("_preference") or construct.endswith("_tolerance")
    }
    relational_expectations = {
        construct: {"value": value, "origin": "scored-from-subject-responses"}
        for construct, value in project.items()
        if construct.startswith("comfort_") or construct in {"desired_initial_closeness", "preferred_initial_distance"}
    }
    return {
        "self_report_fields": self_report_fields,
        "researcher_coded_fields": researcher_coded_fields,
        "interaction_preferences": interaction_preferences,
        "relational_expectations": relational_expectations,
    }
