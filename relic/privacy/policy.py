"""Privacy policy loader (PR04).

Policies are declarative and live in ``policies/privacy.yaml``.
This module reads the YAML file with no third-party dependency; if PyYAML is
not available it falls back to a minimal parser.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PrivacyPolicy:
    sensitive_categories: list[str] = field(default_factory=list)
    raw_prompt_logging: bool = False
    rehydration_allowed: bool = False
    final_output_gate_enabled: bool = True

    @classmethod
    def default(cls) -> "PrivacyPolicy":
        return cls(
            sensitive_categories=["health", "finance", "credentials", "minors"],
            raw_prompt_logging=False,
            rehydration_allowed=False,
            final_output_gate_enabled=True,
        )


def _parse_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml

        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    out: dict[str, Any] = {}
    cur_key: str | None = None
    for line in text.splitlines():
        s = line.rstrip()
        if not s or s.lstrip().startswith("#"):
            continue
        if s.startswith("  - "):
            if cur_key is None:
                continue
            v = s[4:].strip().strip('"').strip("'")
            out.setdefault(cur_key, []).append(v)
        elif ":" in s and not s.startswith("  "):
            key, _, val = s.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            cur_key = key
            if val == "":
                out[key] = []
            elif val.lower() in ("true", "false"):
                out[key] = val.lower() == "true"
            else:
                out[key] = val
    return out


def load_policy(path: str | Path | None = None) -> PrivacyPolicy:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "policies" / "privacy.yaml"
    p = Path(path)
    if not p.exists():
        return PrivacyPolicy.default()
    data = _parse_yaml(p.read_text())
    return PrivacyPolicy(
        sensitive_categories=list(data.get("sensitive_categories", [])),
        raw_prompt_logging=bool(data.get("raw_prompt_logging", False)),
        rehydration_allowed=bool(data.get("rehydration_allowed", False)),
        final_output_gate_enabled=bool(data.get("final_output_gate_enabled", True)),
    )
