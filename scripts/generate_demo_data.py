#!/usr/bin/env python3
"""
Demo Data Generator for Relic
Generates synthetic SQLite DB and JSON export for researcher console demo.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def hash_content(content: str) -> str:
    """Generate SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def random_hash() -> str:
    """Generate a random SHA256 hash for synthetic data."""
    return hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()


def gen_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:8]}" if prefix else uuid.uuid4().hex[:8]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all required tables per migration schemas."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS lineage_base (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prompt_records (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            content_length INTEGER NOT NULL,
            is_redacted INTEGER DEFAULT 0,
            original_prompt_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_prompt_session ON prompt_records(session_id);
        CREATE INDEX IF NOT EXISTS idx_prompt_hash ON prompt_records(content_hash);
        CREATE TABLE IF NOT EXISTS correction_records (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            prompt_id TEXT NOT NULL,
            correction_type TEXT NOT NULL,
            delta_content TEXT NOT NULL,
            applied INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual'
        );
        CREATE INDEX IF NOT EXISTS idx_correction_prompt ON correction_records(prompt_id);
        CREATE TABLE IF NOT EXISTS artifact_records (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            artifact_hash TEXT NOT NULL,
            lineage_path TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_artifact_session ON artifact_records(session_id);
        CREATE INDEX IF NOT EXISTS idx_artifact_hash ON artifact_records(artifact_hash);
        CREATE TABLE IF NOT EXISTS consent_records (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT NOT NULL,
            consent_type TEXT NOT NULL,
            granted INTEGER DEFAULT 0,
            scope TEXT DEFAULT 'session'
        );
        CREATE INDEX IF NOT EXISTS idx_consent_session ON consent_records(session_id);
        CREATE TABLE IF NOT EXISTS pause_records (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resumed_at TIMESTAMP,
            session_id TEXT,
            state TEXT NOT NULL DEFAULT 'paused',
            reason TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_pause_session ON pause_records(session_id);
        CREATE TABLE IF NOT EXISTS incident_reports (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            session_id TEXT,
            metadata_json TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_incident_status ON incident_reports(status);
        CREATE INDEX IF NOT EXISTS idx_incident_severity ON incident_reports(severity);
        CREATE TABLE IF NOT EXISTS quarantined_artifacts (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            incident_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            artifact_hash TEXT NOT NULL,
            quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT NOT NULL,
            session_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_quarantine_incident ON quarantined_artifacts(incident_id);
        CREATE TABLE IF NOT EXISTS prompt_artifacts (
            prompt_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            relationship_type TEXT DEFAULT 'derived',
            PRIMARY KEY (prompt_id, artifact_id)
        );
        CREATE INDEX IF NOT EXISTS idx_prompt_artifact_prompt ON prompt_artifacts(prompt_id);
        CREATE INDEX IF NOT EXISTS idx_prompt_artifact_artifact ON prompt_artifacts(artifact_id);
        INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0001', CURRENT_TIMESTAMP);
        INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0002', CURRENT_TIMESTAMP);
    """)
    conn.commit()


def generate_synthetic_data(conn: sqlite3.Connection, base_time: datetime) -> dict:
    """Generate and insert all synthetic records."""
    sessions = ["sess_001", "sess_002", "sess_003"]
    session_times = [
        base_time - timedelta(days=6, hours=12),
        base_time - timedelta(days=3, hours=8),
        base_time - timedelta(hours=18),
    ]
    
    # Track IDs for relationships
    prompt_ids = []
    correction_types = ["factual_correction", "tone_adjustment", "privacy_redaction", "factual_correction", "scope_clarification"]
    artifact_types = ["portrait", "trait_snapshot", "hypothesis", "correction_bundle", "session_summary", "lineage_graph"]
    
    data = {
        "sessions": [],
        "prompt_records": [],
        "correction_records": [],
        "artifact_records": [],
        "consent_records": [],
        "incident_reports": [],
        "pause_records": [],
    }
    
    # Insert prompt records (8 total across 3 sessions)
    prompt_data = [
        # sess_001 (3 prompts)
        {"session": "sess_001", "role": "user", "redacted": 0, "content": "Initial profile query"},
        {"session": "sess_001", "role": "assistant", "redacted": 0, "content": "Profile response"},
        {"session": "sess_001", "role": "user", "redacted": 1, "content": "Sensitive correction request"},
        # sess_002 (3 prompts)
        {"session": "sess_002", "role": "user", "redacted": 0, "content": "Follow-up interaction"},
        {"session": "sess_002", "role": "assistant", "redacted": 0, "content": "Updated response"},
        {"session": "sess_002", "role": "user", "redacted": 1, "content": "Privacy-sensitive edit"},
        # sess_003 (2 prompts)
        {"session": "sess_003", "role": "user", "redacted": 0, "content": "Final query"},
        {"session": "sess_003", "role": "assistant", "redacted": 0, "content": "Summary response"},
    ]
    
    prompt_idx = 0
    for i, pd in enumerate(prompt_data):
        sess_idx = int(pd["session"].split("_")[1]) - 1
        created_at = session_times[sess_idx] + timedelta(minutes=i * 15)
        pid = f"prompt_{gen_id()}"
        prompt_ids.append(pid)
        content_hash = hash_content(pd["content"])
        content_length = len(pd["content"])
        
        conn.execute("""
            INSERT INTO prompt_records (id, created_at, updated_at, session_id, role, content_hash, content_length, is_redacted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, created_at.isoformat(), created_at.isoformat(), pd["session"], pd["role"], content_hash, content_length, pd["redacted"]))
        
        data["prompt_records"].append({
            "id": pid,
            "created_at": created_at.isoformat(),
            "session_id": pd["session"],
            "role": pd["role"],
            "content_hash": content_hash,
            "content_length": content_length,
            "is_redacted": pd["redacted"],
        })
    
    # Insert correction records (5 total)
    correction_data = [
        {"prompt_idx": 0, "type": "factual_correction", "delta": "Fixed date reference from March to April", "applied": 1, "source": "manual"},
        {"prompt_idx": 1, "type": "tone_adjustment", "delta": "Softened language to be less formal", "applied": 1, "source": "compiler"},
        {"prompt_idx": 2, "type": "privacy_redaction", "delta": "Redacted personal identifier from content", "applied": 1, "source": "manual"},
        {"prompt_idx": 3, "type": "factual_correction", "delta": "Corrected numerical value in response", "applied": 0, "source": "manual"},
        {"prompt_idx": 4, "type": "scope_clarification", "delta": "Added scope limitation note to summary", "applied": 0, "source": "compiler"},
    ]
    
    for i, cd in enumerate(correction_data):
        corr_id = f"corr_{gen_id()}"
        created_at = session_times[1] + timedelta(minutes=len(correction_data) * 10 + i * 5)
        conn.execute("""
            INSERT INTO correction_records (id, created_at, updated_at, prompt_id, correction_type, delta_content, applied, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (corr_id, created_at.isoformat(), created_at.isoformat(), prompt_ids[cd["prompt_idx"]], cd["type"], cd["delta"], cd["applied"], cd["source"]))
        
        data["correction_records"].append({
            "id": corr_id,
            "created_at": created_at.isoformat(),
            "prompt_id": prompt_ids[cd["prompt_idx"]],
            "correction_type": cd["type"],
            "delta_content": cd["delta"],
            "applied": cd["applied"],
            "source": cd["source"],
        })
    
    # Insert artifact records (6 total)
    artifact_data = [
        {"session": "sess_001", "type": "portrait", "lineage": "sess_001/extract/synthesize/portrait", "metadata": {"version": "1", "subject": "demo-subject"}},
        {"session": "sess_001", "type": "trait_snapshot", "lineage": "sess_001/extract/traits/snapshot", "metadata": {"version": "1", "subject": "demo-subject"}},
        {"session": "sess_002", "type": "hypothesis", "lineage": "sess_002/analyze/hypothesis/generate", "metadata": {"version": "1", "subject": "demo-subject"}},
        {"session": "sess_002", "type": "correction_bundle", "lineage": "sess_002/correct/bundle/apply", "metadata": {"version": "1", "subject": "demo-subject"}},
        {"session": "sess_003", "type": "session_summary", "lineage": "sess_003/summarize/session/final", "metadata": {"version": "1", "subject": "demo-subject"}},
        {"session": "sess_003", "type": "lineage_graph", "lineage": "sess_003/lineage/graph/export", "metadata": {"version": "1", "subject": "demo-subject"}},
    ]
    
    for ad in artifact_data:
        art_id = f"art_{gen_id()}"
        artifact_hash = random_hash()
        sess_idx = int(ad["session"].split("_")[1]) - 1
        created_at = session_times[sess_idx] + timedelta(minutes=45)
        
        conn.execute("""
            INSERT INTO artifact_records (id, created_at, updated_at, session_id, artifact_type, artifact_hash, lineage_path, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (art_id, created_at.isoformat(), created_at.isoformat(), ad["session"], ad["type"], artifact_hash, ad["lineage"], json.dumps(ad["metadata"])))
        
        data["artifact_records"].append({
            "id": art_id,
            "created_at": created_at.isoformat(),
            "session_id": ad["session"],
            "artifact_type": ad["type"],
            "artifact_hash": artifact_hash,
            "lineage_path": ad["lineage"],
            "metadata_json": ad["metadata"],
        })
    
    # Insert consent records (4 total)
    consent_data = [
        {"session": "sess_001", "type": "data_collection", "granted": 1, "scope": "session"},
        {"session": "sess_001", "type": "profile_inference", "granted": 1, "scope": "persistent"},
        {"session": "sess_002", "type": "correction_review", "granted": 1, "scope": "session"},
        {"session": "sess_003", "type": "export", "granted": 0, "scope": "session"},
    ]
    
    for cd in consent_data:
        cons_id = f"cons_{gen_id()}"
        sess_idx = int(cd["session"].split("_")[1]) - 1
        created_at = session_times[sess_idx]
        
        conn.execute("""
            INSERT INTO consent_records (id, created_at, updated_at, session_id, consent_type, granted, scope)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cons_id, created_at.isoformat(), created_at.isoformat(), cd["session"], cd["type"], cd["granted"], cd["scope"]))
        
        data["consent_records"].append({
            "id": cons_id,
            "created_at": created_at.isoformat(),
            "session_id": cd["session"],
            "consent_type": cd["type"],
            "granted": cd["granted"],
            "scope": cd["scope"],
        })
    
    # Insert incident reports (2 total)
    incident_data = [
        {"severity": "medium", "status": "open", "title": "Potential PII detection in prompt", "description": "Automated scan flagged possible personal identifier in session interaction", "session": "sess_001"},
        {"severity": "low", "status": "resolved", "title": "Unusual API response pattern", "description": "Detected atypical response length suggesting possible generation anomaly", "session": "sess_002"},
    ]
    
    for inc in incident_data:
        inc_id = f"inc_{gen_id()}"
        sess_idx = int(inc["session"].split("_")[1]) - 1
        created_at = session_times[sess_idx] + timedelta(hours=2)
        resolved_at = created_at + timedelta(hours=1) if inc["status"] == "resolved" else None
        
        conn.execute("""
            INSERT INTO incident_reports (id, created_at, updated_at, resolved_at, severity, status, title, description, session_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (inc_id, created_at.isoformat(), created_at.isoformat(), resolved_at.isoformat() if resolved_at else None, inc["severity"], inc["status"], inc["title"], inc["description"], inc["session"], "{}"))
        
        data["incident_reports"].append({
            "id": inc_id,
            "created_at": created_at.isoformat(),
            "resolved_at": resolved_at.isoformat() if resolved_at else None,
            "severity": inc["severity"],
            "status": inc["status"],
            "title": inc["title"],
            "description": inc["description"],
            "session_id": inc["session"],
        })
    
    # Insert pause records (2 total)
    pause_data = [
        {"session": "sess_002", "state": "resumed", "reason": "Scheduled maintenance window", "paused": True, "resumed": True},
        {"session": "sess_003", "state": "paused", "reason": "Manual pause by researcher", "paused": True, "resumed": False},
    ]
    
    for pd in pause_data:
        pause_id = f"pause_{gen_id()}"
        sess_idx = int(pd["session"].split("_")[1]) - 1
        initiated_at = session_times[sess_idx] + timedelta(hours=1)
        resumed_at = initiated_at + timedelta(minutes=30) if pd["resumed"] else None
        
        conn.execute("""
            INSERT INTO pause_records (id, created_at, updated_at, initiated_at, resumed_at, session_id, state, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pause_id, initiated_at.isoformat(), datetime.now(timezone.utc).isoformat(), initiated_at.isoformat(), resumed_at.isoformat() if resumed_at else None, pd["session"], pd["state"], pd["reason"]))
        
        data["pause_records"].append({
            "id": pause_id,
            "created_at": initiated_at.isoformat(),
            "initiated_at": initiated_at.isoformat(),
            "resumed_at": resumed_at.isoformat() if resumed_at else None,
            "session_id": pd["session"],
            "state": pd["state"],
            "reason": pd["reason"],
        })
    
    # Build session summaries
    for i, sess in enumerate(sessions):
        prompts = [p for p in data["prompt_records"] if p["session_id"] == sess]
        consents = [c for c in data["consent_records"] if c["session_id"] == sess]
        granted = sum(1 for c in consents if c["granted"] == 1)
        
        data["sessions"].append({
            "id": sess,
            "created_at": session_times[i].isoformat(),
            "prompt_count": len(prompts),
            "redacted_count": sum(1 for p in prompts if p["is_redacted"] == 1),
            "consent_granted": granted,
            "consent_total": len(consents),
        })
    
    conn.commit()
    return data


def compute_stats(data: dict) -> dict:
    """Compute summary statistics."""
    corrections_applied = sum(1 for c in data["correction_records"] if c["applied"] == 1)
    corrections_pending = sum(1 for c in data["correction_records"] if c["applied"] == 0)
    open_incidents = sum(1 for i in data["incident_reports"] if i["status"] == "open")
    
    return {
        "total_sessions": len(data["sessions"]),
        "total_prompts": len(data["prompt_records"]),
        "redacted_prompts": sum(1 for p in data["prompt_records"] if p["is_redacted"] == 1),
        "corrections_applied": corrections_applied,
        "corrections_pending": corrections_pending,
        "artifacts": len(data["artifact_records"]),
        "consent_granted": sum(1 for c in data["consent_records"] if c["granted"] == 1),
        "open_incidents": open_incidents,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate demo data for Relic researcher console")
    parser.add_argument("--out-dir", default="demo/generated", help="Output directory for generated files")
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = out_dir / "relic_demo.db"
    json_path = out_dir / "demo_data.json"
    
    base_time = datetime.now(timezone.utc)
    
    # Create database
    conn = sqlite3.connect(str(db_path))
    create_tables(conn)
    
    # Generate and insert synthetic data
    data = generate_synthetic_data(conn, base_time)
    conn.close()
    
    # Compute stats
    stats = compute_stats(data)
    
    # Build export
    export = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subject": "demo-subject",
        "sessions": data["sessions"],
        "prompt_records": data["prompt_records"],
        "correction_records": data["correction_records"],
        "artifact_records": data["artifact_records"],
        "consent_records": data["consent_records"],
        "incident_reports": data["incident_reports"],
        "pause_records": data["pause_records"],
        "stats": stats,
    }
    
    # Write JSON
    with open(json_path, "w") as f:
        json.dump(export, f, indent=2)
    
    # Print summary
    print("=" * 50)
    print("DEMO DATA GENERATOR - SUMMARY")
    print("=" * 50)
    print(f"Database: {db_path}")
    print(f"JSON export: {json_path}")
    print()
    print("Statistics:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()
    print("Sessions:")
    for s in data["sessions"]:
        print(f"  {s['id']}: {s['prompt_count']} prompts, {s['redacted_count']} redacted, consent: {s['consent_granted']}/{s['consent_total']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
