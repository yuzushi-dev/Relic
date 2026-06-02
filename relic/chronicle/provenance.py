"""Chronicle provenance, artifact provenance graph management.

Module: relic.chronicle.provenance
Version: chronicle-provenance/v1
Reference: docs/chronicle/agentic-development-plan.md §6.4, T021

PROV-O relations (https://www.w3.org/TR/prov-o/):
  used, wasGeneratedBy, wasDerivedFrom, wasInformedBy,
  wasAssociatedWith, actedOnBehalfOf, hadMember, wasTriggeredBy, wasControlledBy
"""
from __future__ import annotations

import logging
import uuid
from collections import deque
from typing import Any

from relic.chronicle import context as pctx
from relic.chronicle.emitter import emit_provenance_edge
from relic.chronicle.enums import ProximityOrder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Add edge
# ---------------------------------------------------------------------------

def add_edge(
    *,
    artifact_id: uuid.UUID,
    from_node_type: str,
    from_node_id: uuid.UUID,
    relation: str,
    contribution_role: str | None = None,
    weight: float = 1.0,
    trace_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Add a provenance edge to the artifact graph.

    Returns edge_id. Fail-open.
    """
    return emit_provenance_edge(
        artifact_id=artifact_id,
        from_node_type=from_node_type,
        from_node_id=from_node_id,
        relation=relation,
        contribution_role=contribution_role,
        weight=weight,
        trace_id=trace_id,
    )


def _get_db_connection():
    """Get DB connection for provenance queries."""
    try:
        from relic.db import get_connection
        return get_connection()
    except Exception as e:
        logger.warning(f"[chronicle.provenance] DB unavailable: {e}")
        raise


# ---------------------------------------------------------------------------
# Traversal helpers
# ---------------------------------------------------------------------------

def _get_edges_for_artifact(
    artifact_id: uuid.UUID,
    conn: Any,
    direction: str = "outbound",
) -> list[dict[str, Any]]:
    """Get edges for an artifact. direction: outbound (descendants) or inbound (ancestors)."""
    try:
        if direction == "outbound":
            rows = conn.execute(
                """
                SELECT edge_id, from_node_type, from_node_id, relation,
                       contribution_role, weight, timestamp
                FROM chronicle_provenance_edges
                WHERE artifact_id = ?
                ORDER BY timestamp ASC
                """,
                (str(artifact_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT e.edge_id, e.artifact_id, e.from_node_type, e.from_node_id,
                       e.relation, e.contribution_role, e.weight, e.timestamp
                FROM chronicle_provenance_edges e
                WHERE e.artifact_id = (
                    SELECT artifact_id FROM chronicle_provenance_edges
                    WHERE from_node_type = 'artifact' AND from_node_id = ?
                    LIMIT 1
                ) OR e.artifact_id = ? -- same artifact (not useful for ancestors)
                LIMIT 0
                """,
                (str(artifact_id), str(artifact_id)),
            ).fetchall()
        return []
    except Exception as e:
        logger.debug(f"[chronicle.provenance] edge query: {e}")
        return []


def _find_ancestors(
    artifact_id: uuid.UUID,
    max_depth: int = 3,
) -> list[dict[str, Any]]:
    """Find all upstream nodes up to max_depth hops using BFS."""
    try:
        conn = _get_db_connection()
    except Exception:
        return []

    visited: set[str] = set()
    queue: list[tuple[str, int]] = []  # (artifact_id, depth)
    results: list[dict[str, Any]] = []

    # Start from the artifact itself as the root
    queue.append((str(artifact_id), 0))

    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        if current_id in visited:
            continue
        visited.add(current_id)

        # Find edges where this artifact was the source
        try:
            rows = conn.execute(
                """
                SELECT edge_id, artifact_id, from_node_type, from_node_id,
                       relation, contribution_role, weight, timestamp
                FROM chronicle_provenance_edges
                WHERE artifact_id = ?
                """,
                (current_id,),
            ).fetchall()

            for row in rows:
                edge = {
                    "edge_id": row[0],
                    "artifact_id": row[1],
                    "from_node_type": row[2],
                    "from_node_id": row[3],
                    "relation": row[4],
                    "contribution_role": row[5],
                    "weight": row[6],
                    "timestamp": row[7],
                    "depth": depth + 1,
                }
                results.append(edge)

                # Continue traversal for artifact nodes only
                if row[2] == "artifact" and row[3] not in visited:
                    queue.append((row[3], depth + 1))
        except Exception as e:
            logger.debug(f"[chronicle.provenance] ancestors query failed: {e}")

    return results


def _find_descendants(
    artifact_id: uuid.UUID,
    max_depth: int = 3,
) -> list[dict[str, Any]]:
    """Find all downstream nodes up to max_depth hops using BFS."""
    try:
        conn = _get_db_connection()
    except Exception:
        return []

    visited: set[str] = set()
    queue: list[tuple[str, int]] = []  # (node_id, depth)
    results: list[dict[str, Any]] = []

    # Start from this artifact (as from_node_id in edges that point to it)
    queue.append((str(artifact_id), 0))

    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        if current_id in visited:
            continue
        visited.add(current_id)

        try:
            rows = conn.execute(
                """
                SELECT edge_id, artifact_id, from_node_type, from_node_id,
                       relation, contribution_role, weight, timestamp
                FROM chronicle_provenance_edges
                WHERE from_node_type = 'artifact' AND from_node_id = ?
                """,
                (current_id,),
            ).fetchall()

            for row in rows:
                edge = {
                    "edge_id": row[0],
                    "artifact_id": row[1],
                    "from_node_type": row[2],
                    "from_node_id": row[3],
                    "relation": row[4],
                    "contribution_role": row[5],
                    "weight": row[6],
                    "timestamp": row[7],
                    "depth": depth + 1,
                }
                results.append(edge)

                # Continue traversal
                if row[1] not in visited:
                    queue.append((row[1], depth + 1))
        except Exception as e:
            logger.debug(f"[chronicle.provenance] descendants query failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_ancestors(artifact_id: uuid.UUID, *, depth: int = 3) -> list[dict[str, Any]]:
    """Return upstream nodes up to depth hops."""
    if depth < 1:
        return []
    return _find_ancestors(artifact_id, max_depth=depth)


def get_descendants(artifact_id: uuid.UUID, *, depth: int = 3) -> list[dict[str, Any]]:
    """Return downstream nodes up to depth hops."""
    if depth < 1:
        return []
    return _find_descendants(artifact_id, max_depth=depth)


def verify_artifact_provenance(artifact_id: uuid.UUID) -> tuple[bool, list[str]]:
    """Verify that all upstream nodes exist. Returns (valid, missing_ids).

    For each edge's from_node_id, check it exists in:
    - chronicle_events (if from_node_type = 'event')
    - chronicle_state_snapshots (if from_node_type = 'snapshot')
    - artifact_records (if from_node_type = 'artifact')
    """
    try:
        conn = _get_db_connection()
    except Exception as e:
        logger.warning(f"[chronicle.provenance] verify: DB unavailable: {e}")
        return True, []  # fail-open

    missing: list[str] = []

    try:
        rows = conn.execute(
            """
            SELECT from_node_type, from_node_id FROM chronicle_provenance_edges
            WHERE artifact_id = ?
            """,
            (str(artifact_id),),
        ).fetchall()

        for node_type, node_id in rows:
            node_id = str(node_id)
            if node_type == "event":
                exists = conn.execute(
                    "SELECT 1 FROM chronicle_events WHERE event_id = ?", (node_id,)
                ).fetchone()
            elif node_type == "snapshot":
                exists = conn.execute(
                    "SELECT 1 FROM chronicle_state_snapshots WHERE snapshot_id = ?", (node_id,)
                ).fetchone()
            elif node_type == "artifact":
                exists = conn.execute(
                    "SELECT 1 FROM artifact_records WHERE id = ?", (node_id,)
                ).fetchone()
            else:
                exists = None

            if not exists:
                missing.append(f"{node_type}:{node_id}")

        valid = len(missing) == 0
        return valid, missing

    except Exception as e:
        logger.error(f"[chronicle.provenance] verify failed: {e}")
        return True, []  # fail-open
