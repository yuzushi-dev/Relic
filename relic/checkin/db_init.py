"""Initialize relic.db schema and seed the 60-facet registry.

Usage:
    python -m relic.checkin.db_init --subject-id daniele
    python -m relic.checkin.db_init --subject-id daniele --db-path /path/to/relic.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS facets (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    spectrum_low TEXT,
    spectrum_high TEXT,
    sensitivity TEXT DEFAULT 'media',
    intrusion_base REAL DEFAULT 0.45,
    half_life_days INTEGER DEFAULT 60
);

CREATE TABLE IF NOT EXISTS traits (
    facet_id TEXT PRIMARY KEY REFERENCES facets(id),
    value_position REAL,
    confidence REAL DEFAULT 0.0,
    observation_count INTEGER DEFAULT 0,
    last_observation_at TEXT,
    last_synthesis_at TEXT,
    status TEXT DEFAULT 'insufficient_data',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facet_id TEXT NOT NULL REFERENCES facets(id),
    source_type TEXT NOT NULL,
    source_ref TEXT,
    content TEXT NOT NULL,
    extracted_signal TEXT,
    signal_strength REAL DEFAULT 0.5,
    signal_position REAL,
    context TEXT,
    conversation_domain TEXT,
    context_metadata TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(facet_id, source_ref)
);

CREATE TABLE IF NOT EXISTS checkin_exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facet_id TEXT REFERENCES facets(id),
    question_text TEXT NOT NULL,
    reply_text TEXT,
    reply_captured_at TEXT,
    observations_extracted INTEGER DEFAULT 0,
    asked_at TEXT NOT NULL,
    message_id TEXT,
    followup_sent_at TEXT
);

CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis TEXT NOT NULL,
    status TEXT DEFAULT 'unverified',
    supporting_observations TEXT,
    contradicting_observations TEXT,
    confidence REAL DEFAULT 0.3,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE,
    from_id TEXT NOT NULL,
    content TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS model_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    total_observations INTEGER,
    avg_confidence REAL,
    coverage_pct REAL,
    snapshot_data TEXT
);

CREATE INDEX IF NOT EXISTS idx_observations_facet ON observations(facet_id);
CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_type);
CREATE INDEX IF NOT EXISTS idx_inbox_processed ON inbox(processed);
CREATE INDEX IF NOT EXISTS idx_checkin_unprocessed ON checkin_exchanges(observations_extracted);
CREATE INDEX IF NOT EXISTS idx_checkin_pending ON checkin_exchanges(asked_at DESC) WHERE reply_text IS NULL AND facet_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_checkin_processable ON checkin_exchanges(asked_at) WHERE reply_text IS NOT NULL AND observations_extracted = 0;
CREATE INDEX IF NOT EXISTS idx_observations_source_date ON observations(source_type, created_at);
CREATE INDEX IF NOT EXISTS idx_inbox_pending ON inbox(received_at) WHERE processed = 0;
"""

# 60 canonical facets — derived from the Relic longitudinal model
# Source: cognitive/personality psychology frameworks (Big Five, ECR-R, DERS, CAPS, SDT, Schwartz, LIWC)
FACETS: list[dict] = [
    # cognitive
    {"id": "cognitive.decision_speed",       "category": "cognitive",       "name": "decision_speed",       "description": "Velocità nel prendere decisioni: impulsivo vs deliberato",                     "spectrum_low": "impulsivo",           "spectrum_high": "deliberato",              "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "cognitive.risk_tolerance",       "category": "cognitive",       "name": "risk_tolerance",       "description": "Propensione al rischio nelle scelte",                                        "spectrum_low": "risk-averse",         "spectrum_high": "risk-seeking",            "sensitivity": "media",  "intrusion_base": 0.40},
    {"id": "cognitive.abstraction_level",    "category": "cognitive",       "name": "abstraction_level",    "description": "Livello di astrazione nel ragionamento",                                     "spectrum_low": "concreto",            "spectrum_high": "astratto",                "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "cognitive.information_gathering","category": "cognitive",       "name": "information_gathering","description": "Approccio alla raccolta informazioni: basta abbastanza vs vuole il meglio",  "spectrum_low": "satisficer",          "spectrum_high": "maximizer",               "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "cognitive.analytical_approach",  "category": "cognitive",       "name": "analytical_approach",  "description": "Approccio analitico: intuitivo vs sistematico",                              "spectrum_low": "intuitivo",           "spectrum_high": "sistematico",             "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "cognitive.learning_style",       "category": "cognitive",       "name": "learning_style",       "description": "Stile di apprendimento: pratica prima o teoria prima",                       "spectrum_low": "practice-first",      "spectrum_high": "theory-first",            "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "cognitive.mental_model_complexity","category": "cognitive",     "name": "mental_model_complexity","description": "Complessità dei modelli mentali interni",                                  "spectrum_low": "modelli minimali",    "spectrum_high": "modelli esaustivi",       "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "cognitive.system1_dominance",    "category": "cognitive",       "name": "system1_dominance",    "description": "Dominanza Sistema 1: intuitivo/rapido vs deliberato/analitico",              "spectrum_low": "deliberato/analitico","spectrum_high": "intuitivo/rapido",        "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "cognitive.construct_complexity", "category": "cognitive",       "name": "construct_complexity", "description": "Complessità del sistema di costrutti personali",                            "spectrum_low": "pochi costrutti rigidi","spectrum_high": "molti costrutti flessibili","sensitivity": "bassa","intrusion_base": 0.30},
    # emotional
    {"id": "emotional.stress_response",      "category": "emotional",       "name": "stress_response",      "description": "Risposta allo stress: freeze/evita vs fight/affronta",                      "spectrum_low": "freeze/evita",        "spectrum_high": "fight/affronta",          "sensitivity": "alta",   "intrusion_base": 0.65},
    {"id": "emotional.emotional_granularity","category": "emotional",       "name": "emotional_granularity","description": "Granularità emotiva: generico vs articolato nel descrivere emozioni",       "spectrum_low": "emotivamente generico","spectrum_high": "emotivamente articolato", "sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "emotional.resilience_pattern",   "category": "emotional",       "name": "resilience_pattern",   "description": "Pattern di resilienza: recovery lento vs bounce-back rapido",               "spectrum_low": "recovery lento",      "spectrum_high": "bounce-back rapido",      "sensitivity": "alta",   "intrusion_base": 0.55},
    {"id": "emotional.frustration_triggers", "category": "emotional",       "name": "frustration_triggers", "description": "Soglia di frustrazione: alta soglia vs bassa soglia",                       "spectrum_low": "alta soglia",         "spectrum_high": "bassa soglia",            "sensitivity": "alta",   "intrusion_base": 0.60},
    {"id": "emotional.joy_sources",          "category": "emotional",       "name": "joy_sources",          "description": "Fonti di soddisfazione: strumentale vs intrinseca",                         "spectrum_low": "soddisfazione strumentale","spectrum_high": "soddisfazione intrinseca","sensitivity": "media","intrusion_base": 0.40},
    {"id": "emotional.emotional_expression", "category": "emotional",       "name": "emotional_expression", "description": "Espressione emotiva: contenuto vs espressivo",                               "spectrum_low": "contenuto",           "spectrum_high": "espressivo",              "sensitivity": "media",  "intrusion_base": 0.50},
    {"id": "emotional.emotion_clarity",      "category": "emotional",       "name": "emotion_clarity",      "description": "Chiarezza emotiva (DERS): capacità di identificare le proprie emozioni",   "spectrum_low": "bassa chiarezza",     "spectrum_high": "alta chiarezza",          "sensitivity": "alta",   "intrusion_base": 0.60},
    {"id": "emotional.distress_tolerance",   "category": "emotional",       "name": "distress_tolerance",   "description": "Tolleranza al distress (DERS): funzionamento durante stati emotivi intensi","spectrum_low": "bassa tolleranza",    "spectrum_high": "alta tolleranza",         "sensitivity": "alta",   "intrusion_base": 0.65},
    {"id": "emotional.appraisal_agency",     "category": "emotional",       "name": "appraisal_agency",     "description": "Attribuzione causale nelle situazioni emotive",                             "spectrum_low": "attribuzione esterna","spectrum_high": "attribuzione interna",    "sensitivity": "alta",   "intrusion_base": 0.60},
    {"id": "emotional.coping_appraisal",     "category": "emotional",       "name": "coping_appraisal",     "description": "Valutazione di coping: senso di controllo e capacità di fronteggiare",     "spectrum_low": "basso senso di controllo","spectrum_high": "alto senso di controllo","sensitivity": "alta",  "intrusion_base": 0.65},
    # communication
    {"id": "communication.verbosity",        "category": "communication",   "name": "verbosity",            "description": "Verbosità comunicativa: telegrafico vs elaborato",                          "spectrum_low": "telegrafico",         "spectrum_high": "elaborato",               "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "communication.directness",       "category": "communication",   "name": "directness",           "description": "Stile comunicativo: diplomatico vs schietto",                               "spectrum_low": "diplomatico",         "spectrum_high": "schietto",                "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "communication.humor_type",       "category": "communication",   "name": "humor_type",           "description": "Uso dell'umorismo: serio/raro vs humor frequente",                          "spectrum_low": "serio/raro",          "spectrum_high": "humor frequente",         "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "communication.conflict_style",   "category": "communication",   "name": "conflict_style",       "description": "Stile nel conflitto: evitante vs confrontativo",                            "spectrum_low": "evitante",            "spectrum_high": "confrontativo",           "sensitivity": "alta",   "intrusion_base": 0.60},
    {"id": "communication.storytelling_tendency","category": "communication","name": "storytelling_tendency","description": "Tendenza narrativa: fattuale/dati vs aneddotico/narrativo",               "spectrum_low": "fattuale/dati",       "spectrum_high": "aneddotico/narrativo",    "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "communication.formality_range",  "category": "communication",   "name": "formality_range",      "description": "Range di formalità: sempre informale vs adatta al contesto",               "spectrum_low": "sempre informale",    "spectrum_high": "adatta al contesto",      "sensitivity": "bassa",  "intrusion_base": 0.25},
    # relational
    {"id": "relational.trust_formation",     "category": "relational",      "name": "trust_formation",      "description": "Formazione della fiducia: lenta vs veloce",                                 "spectrum_low": "fiducia lenta",       "spectrum_high": "fiducia veloce",          "sensitivity": "alta",   "intrusion_base": 0.55},
    {"id": "relational.boundary_style",      "category": "relational",      "name": "boundary_style",       "description": "Stile dei confini personali: rigidi vs flessibili",                         "spectrum_low": "confini rigidi",      "spectrum_high": "confini flessibili",      "sensitivity": "alta",   "intrusion_base": 0.60},
    {"id": "relational.loyalty_pattern",     "category": "relational",      "name": "loyalty_pattern",      "description": "Pattern di lealtà: condizionale vs incondizionata",                        "spectrum_low": "lealtà condizionale", "spectrum_high": "lealtà incondizionata",   "sensitivity": "alta",   "intrusion_base": 0.55},
    {"id": "relational.social_energy",       "category": "relational",      "name": "social_energy",        "description": "Energia sociale: introverso vs estroverso",                                 "spectrum_low": "introverso",          "spectrum_high": "estroverso",              "sensitivity": "media",  "intrusion_base": 0.35},
    {"id": "relational.help_seeking",        "category": "relational",      "name": "help_seeking",         "description": "Ricerca di aiuto: indipendente vs collaborativo",                           "spectrum_low": "indipendente",        "spectrum_high": "collaborativo",           "sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "relational.feedback_preference", "category": "relational",      "name": "feedback_preference",  "description": "Preferenza feedback: critica diretta vs feedback mediato",                  "spectrum_low": "critica diretta",     "spectrum_high": "feedback mediato",        "sensitivity": "media",  "intrusion_base": 0.40},
    {"id": "relational.attachment_anxiety",  "category": "relational",      "name": "attachment_anxiety",   "description": "Ansia da attaccamento (ECR-R): paura di rifiuto/abbandono",                "spectrum_low": "bassa ansia",         "spectrum_high": "alta ansia",              "sensitivity": "alta",   "intrusion_base": 0.70},
    {"id": "relational.attachment_avoidance","category": "relational",      "name": "attachment_avoidance", "description": "Evitamento da attaccamento (ECR-R): disagio con la vicinanza emotiva",     "spectrum_low": "basso evitamento",    "spectrum_high": "alto evitamento",         "sensitivity": "alta",   "intrusion_base": 0.70},
    {"id": "relational.vulnerability_capacity","category": "relational",    "name": "vulnerability_capacity","description": "Capacità di mostrarsi vulnerabile",                                       "spectrum_low": "bassa capacità",      "spectrum_high": "alta capacità",           "sensitivity": "alta",   "intrusion_base": 0.65},
    # values
    {"id": "values.fairness_model",          "category": "values",          "name": "fairness_model",       "description": "Modello di equità: meritocratico vs egualitario",                           "spectrum_low": "meritocratico",       "spectrum_high": "egualitario",             "sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "values.authority_stance",        "category": "values",          "name": "authority_stance",     "description": "Posizione verso l'autorità: rispetta gerarchia vs sfida l'autorità",       "spectrum_low": "rispetta la gerarchia","spectrum_high": "sfida l'autorità",       "sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "values.autonomy_importance",     "category": "values",          "name": "autonomy_importance",  "description": "Importanza dell'autonomia: team-oriented vs indipendenza forte",            "spectrum_low": "team-oriented",       "spectrum_high": "indipendenza forte",      "sensitivity": "media",  "intrusion_base": 0.40},
    {"id": "values.aesthetic_values",        "category": "values",          "name": "aesthetic_values",     "description": "Valori estetici: funzionale/pragmatico vs eleganza/bellezza",              "spectrum_low": "funzionale/pragmatico","spectrum_high": "eleganza/bellezza",      "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "values.work_ethic",              "category": "values",          "name": "work_ethic",           "description": "Etica del lavoro: output-oriented vs effort-oriented",                      "spectrum_low": "output-oriented",     "spectrum_high": "effort-oriented",         "sensitivity": "media",  "intrusion_base": 0.40},
    {"id": "values.schwartz_self_enhancement","category": "values",         "name": "schwartz_self_enhancement","description": "Valori Schwartz: auto-trascendenza vs auto-affermazione",             "spectrum_low": "auto-trascendenza",   "spectrum_high": "auto-affermazione",       "sensitivity": "media",  "intrusion_base": 0.50},
    # temporal
    {"id": "temporal.planning_horizon",      "category": "temporal",        "name": "planning_horizon",     "description": "Orizzonte di pianificazione: presente vs lungo termine",                   "spectrum_low": "vive nel presente",   "spectrum_high": "pianifica a lungo termine","sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "temporal.routine_attachment",    "category": "temporal",        "name": "routine_attachment",   "description": "Attaccamento alla routine: cerca varietà vs ama la routine",               "spectrum_low": "cerca varietà",       "spectrum_high": "ama la routine",          "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "temporal.deadline_behavior",     "category": "temporal",        "name": "deadline_behavior",    "description": "Comportamento con le scadenze: last-minute vs finisce in anticipo",       "spectrum_low": "last-minute",         "spectrum_high": "finisce in anticipo",     "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "temporal.nostalgia_tendency",    "category": "temporal",        "name": "nostalgia_tendency",   "description": "Tendenza alla nostalgia: proiettato al futuro vs orientato al passato",    "spectrum_low": "proiettato al futuro","spectrum_high": "orientato al passato",    "sensitivity": "media",  "intrusion_base": 0.40},
    {"id": "temporal.patience_threshold",    "category": "temporal",        "name": "patience_threshold",   "description": "Soglia di pazienza: impaziente vs paziente",                               "spectrum_low": "impaziente",          "spectrum_high": "paziente",                "sensitivity": "bassa",  "intrusion_base": 0.30},
    {"id": "temporal.delay_discounting",     "category": "temporal",        "name": "delay_discounting",    "description": "Sconto temporale: ricompense immediate vs differite (SDT)",               "spectrum_low": "impulsivo (preferisce ora)","spectrum_high": "paziente (differisce)", "sensitivity": "media",  "intrusion_base": 0.45},
    # aesthetic
    {"id": "aesthetic.design_sensibility",   "category": "aesthetic",       "name": "design_sensibility",   "description": "Sensibilità al design: massimalista vs minimalista",                       "spectrum_low": "massimalista",        "spectrum_high": "minimalista",             "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "aesthetic.media_consumption",    "category": "aesthetic",       "name": "media_consumption",    "description": "Consumo media: passivo/mainstream vs attivo/di nicchia",                   "spectrum_low": "passivo/mainstream",  "spectrum_high": "attivo/di nicchia",       "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "aesthetic.food_preferences",     "category": "aesthetic",       "name": "food_preferences",     "description": "Preferenze alimentari: comfort/abitudinario vs avventuroso",              "spectrum_low": "comfort/abitudinario","spectrum_high": "avventuroso",             "sensitivity": "bassa",  "intrusion_base": 0.20},
    {"id": "aesthetic.environment_preference","category": "aesthetic",      "name": "environment_preference","description": "Preferenza ambiente: caotico/stimolante vs ordinato/minimal",            "spectrum_low": "caotico/stimolante",  "spectrum_high": "ordinato/minimal",        "sensitivity": "bassa",  "intrusion_base": 0.25},
    # meta_cognition
    {"id": "meta_cognition.self_awareness",  "category": "meta_cognition",  "name": "self_awareness",       "description": "Consapevolezza di sé: bassa vs alta",                                      "spectrum_low": "bassa consapevolezza","spectrum_high": "alta consapevolezza",     "sensitivity": "alta",   "intrusion_base": 0.55},
    {"id": "meta_cognition.growth_mindset",  "category": "meta_cognition",  "name": "growth_mindset",       "description": "Mentalità di crescita: fixed vs growth mindset",                           "spectrum_low": "fixed mindset",       "spectrum_high": "growth mindset",          "sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "meta_cognition.reflection_habit","category": "meta_cognition",  "name": "reflection_habit",     "description": "Abitudine alla riflessione: raramente vs auto-riflessione frequente",     "spectrum_low": "raramente si esamina","spectrum_high": "auto-riflessione frequente","sensitivity": "media", "intrusion_base": 0.45},
    {"id": "meta_cognition.change_readiness","category": "meta_cognition",  "name": "change_readiness",     "description": "Prontezza al cambiamento: resiste vs abbraccia il cambiamento",            "spectrum_low": "resiste al cambiamento","spectrum_high": "abbraccia il cambiamento","sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "meta_cognition.uncertainty_tolerance","category": "meta_cognition","name": "uncertainty_tolerance","description": "Tolleranza all'incertezza: bisogno di certezza vs agio con ambiguità","spectrum_low": "bisogno di certezza", "spectrum_high": "a proprio agio con l'ambiguità","sensitivity": "media","intrusion_base": 0.45},
    {"id": "meta_cognition.narrative_agency","category": "meta_cognition",  "name": "narrative_agency",     "description": "Agency narrativa (McAdams): protagonista vs agito dagli eventi",          "spectrum_low": "si sente agito dagli eventi","spectrum_high": "si sente architetto attivo","sensitivity": "alta","intrusion_base": 0.55},
    # language
    {"id": "language.verbal_complexity",     "category": "language",        "name": "verbal_complexity",    "description": "Complessità verbale: ricchezza vocabolario e struttura frasi",             "spectrum_low": "semplice/diretto",    "spectrum_high": "complesso/elaborato",     "sensitivity": "bassa",  "intrusion_base": 0.25},
    # non-spectrum facets (list/open-ended)
    {"id": "aesthetic.music_taste",          "category": "aesthetic",       "name": "music_taste",          "description": "Gusti musicali (non spettro lineare — generi e pattern)",                 "spectrum_low": None,                  "spectrum_high": None,                      "sensitivity": "bassa",  "intrusion_base": 0.25},
    {"id": "meta_cognition.cognitive_biases","category": "meta_cognition",  "name": "cognitive_biases",     "description": "Bias cognitivi osservati (non spettro — lista di bias)",                  "spectrum_low": None,                  "spectrum_high": None,                      "sensitivity": "media",  "intrusion_base": 0.45},
    {"id": "values.core_values",             "category": "values",          "name": "core_values",          "description": "Valori fondamentali (non spettro lineare — lista di valori)",             "spectrum_low": None,                  "spectrum_high": None,                      "sensitivity": "media",  "intrusion_base": 0.45},
]

if len(FACETS) != 60:
    raise RuntimeError(f"Expected 60 facets, got {len(FACETS)}")


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def seed_facets(conn: sqlite3.Connection) -> int:
    """Insert facet definitions if not already present. Returns count inserted."""
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    for f in FACETS:
        existing = conn.execute("SELECT id FROM facets WHERE id = ?", (f["id"],)).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO facets (id, category, name, description, spectrum_low, spectrum_high, sensitivity, intrusion_base) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f["id"], f["category"], f["name"], f["description"],
             f.get("spectrum_low"), f.get("spectrum_high"),
             f.get("sensitivity", "media"), f.get("intrusion_base", 0.45)),
        )
        conn.execute(
            "INSERT OR IGNORE INTO traits (facet_id, status) VALUES (?, 'insufficient_data')",
            (f["id"],),
        )
        inserted += 1
    conn.commit()
    return inserted


def get_db_path(subject_id: str, relic_home: str | None = None) -> Path:
    import os
    home = Path(relic_home or os.environ.get("RELIC_HOME", Path.home() / ".relic"))
    return home / "subjects" / subject_id / "relic.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize relic.db schema and facet registry")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--relic-home", default=None)
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else get_db_path(args.subject_id, args.relic_home)
    conn = init_db(db_path)
    inserted = seed_facets(conn)
    conn.close()
    print(json.dumps({"status": "ok", "db_path": str(db_path), "facets_inserted": inserted}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
