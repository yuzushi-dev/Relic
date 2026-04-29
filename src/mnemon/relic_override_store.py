#!/usr/bin/env python3
"""Override snapshot store — versioning e rollback per gli override dei monitor Paperclip.

Ogni monitor chiama snapshot_before_write() prima di sovrascrivere il proprio file
di override attivo. Gli snapshot vengono salvati in:
    RELIC_DIR/override_snapshots/{team}/{YYYYMMDD_HHMMSS}.json

Vengono mantenuti al massimo MAX_SNAPSHOTS snapshot per team (FIFO).
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_SNAPSHOTS = 20
SNAPSHOT_DIR_NAME = "override_snapshots"


# ── Snapshot ──────────────────────────────────────────────────────────────────

def _snapshots_dir(relic_dir: Path, team: str) -> Path:
    return relic_dir / SNAPSHOT_DIR_NAME / team


def snapshot_before_write(
    override_file: Path, team: str, relic_dir: Path
) -> Path | None:
    """Salva una copia del file corrente (se esiste) prima di sovrascriverlo.

    Ritorna il path dello snapshot salvato, oppure None se il file non esisteva.
    """
    if not override_file.exists():
        return None

    snap_dir = _snapshots_dir(relic_dir, team)
    snap_dir.mkdir(parents=True, exist_ok=True)

    ts_base = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snap_path = snap_dir / f"{ts_base}.json"
    counter = 1
    while snap_path.exists():
        snap_path = snap_dir / f"{ts_base}_{counter:03d}.json"
        counter += 1
    shutil.copy2(override_file, snap_path)

    _prune_old_snapshots(snap_dir)
    return snap_path


def _prune_old_snapshots(snap_dir: Path) -> None:
    snaps = sorted(snap_dir.glob("*.json"))
    for old in snaps[:-MAX_SNAPSHOTS]:
        old.unlink(missing_ok=True)


# ── Query ────────────────────────────────────────────────────────────────────

def list_snapshots(relic_dir: Path, team: str) -> list[dict[str, Any]]:
    """Lista gli snapshot disponibili per il team, dal più recente al più vecchio."""
    snap_dir = _snapshots_dir(relic_dir, team)
    if not snap_dir.exists():
        return []

    result = []
    for f in sorted(snap_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "timestamp": f.stem,
                "path": str(f),
                "severity": data.get("severity", "?"),
                "generated_at": data.get("generated_at", "?"),
                "constraints": [
                    k for k in data
                    if k not in ("severity", "generated_at", "expires_at")
                ],
            })
        except Exception:
            continue
    return result


def get_active_overrides(override_file: Path) -> dict[str, Any] | None:
    """Legge il file di override attivo.

    Ritorna None se il file non esiste o è scaduto.
    """
    if not override_file.exists():
        return None
    try:
        data = json.loads(override_file.read_text(encoding="utf-8"))
        exp = data.get("expires_at")
        if exp and datetime.fromisoformat(exp) < datetime.now(timezone.utc):
            return None
        return data
    except Exception:
        return None


# ── Restore ───────────────────────────────────────────────────────────────────

def restore_snapshot(
    relic_dir: Path,
    team: str,
    override_file: Path,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Ripristina uno snapshot per il team.

    Se timestamp è None, ripristina il più recente.
    Prima di sovrascrivere, salva lo stato corrente come snapshot.
    Ritorna {"restored": timestamp, "severity": ...} oppure {"error": msg}.
    """
    snaps = list_snapshots(relic_dir, team)
    if not snaps:
        return {"error": f"nessuno snapshot disponibile per '{team}'"}

    if timestamp:
        target = next((s for s in snaps if s["timestamp"] == timestamp), None)
        if not target:
            return {"error": f"snapshot '{timestamp}' non trovato per '{team}'"}
    else:
        target = snaps[0]

    snapshot_before_write(override_file, team, relic_dir)
    shutil.copy2(target["path"], override_file)

    return {
        "restored": target["timestamp"],
        "severity": target["severity"],
        "constraints": target["constraints"],
    }


def clear_override(
    relic_dir: Path, team: str, override_file: Path
) -> dict[str, Any]:
    """Rimuove il file di override attivo, salvando uno snapshot prima.

    Equivale a un rollback completo ai default del sistema.
    """
    if not override_file.exists():
        return {"status": "already_clear", "team": team}

    snapshot_before_write(override_file, team, relic_dir)
    override_file.unlink()
    return {"status": "cleared", "team": team}
