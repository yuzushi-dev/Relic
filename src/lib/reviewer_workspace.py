"""reviewer_workspace — export debate and data files to Paperclip reviewer workspaces.

All analyst modules call export_debate() after run_debate() to populate the
reviewer's workspace before submitting the Paperclip issue.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lib.log import info, warn

_SCRIPT = "reviewer_workspace"


def _workspace_root() -> Path:
    return Path(
        os.environ.get(
            "PAPERCLIP_WORKSPACE_ROOT",
            str(Path.home() / ".paperclip" / "instances" / "default" / "workspaces"),
        )
    )


def export_debate(
    reviewer_id: str,
    debate: dict[str, Any],
    extra_files: dict[str, Any],
) -> None:
    """Write debate.json and extra_files to the reviewer workspace.

    Args:
        reviewer_id:  Paperclip agent UUID (from PAPERCLIP_<TEAM>_REVIEWER_ID).
        debate:       Output of run_debate() — written as debate.json.
        extra_files:  Dict of {filename_stem: serializable_data}.
                      Each key becomes <workspace>/<key>.json.
    """
    if not reviewer_id:
        return
    ws = _workspace_root() / reviewer_id
    if not ws.exists():
        warn(_SCRIPT, "workspace_not_found", reviewer_id=reviewer_id[:8])
        return

    try:
        (ws / "debate.json").write_text(
            json.dumps(debate, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        for stem, data in extra_files.items():
            (ws / f"{stem}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        info(
            _SCRIPT,
            "workspace_exported",
            reviewer_id=reviewer_id[:8],
            domain=debate.get("domain", "?"),
            extra_files=list(extra_files.keys()),
        )
    except Exception as exc:
        warn(_SCRIPT, "export_error", reviewer_id=reviewer_id[:8], error=str(exc))
