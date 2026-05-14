"""Multi-subject profile registry for Relic."""

from __future__ import annotations

import json
import os
import re
import hashlib
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from relic.paths import get_relic_home
from relic.hermes_runtime import (
    HERMES_DEFAULT_MODEL,
    HERMES_PROFILE_DEFAULT_MODEL,
    HermesSessionKey,
    register_allowlist_entry,
    render_hindsight_local_config,
    render_subject_hermes_config,
)
from relic.gumi_plugin.cron_wiring import provision_no_agent_cron
from relic.shared_continuity.service import get_continuity_service

VALID_STATES = [
    "draft",
    "baseline_in_progress",
    "baseline_complete",
    "gumi_seed_generated",
    "gumi_seed_reviewed",
    "hermes_profile_provisioned",
    "intro_composed",
    "intro_sent",
    "active",
    "archived",
    "withdrawn",
]

# Allowed transitions (from -> set of valid nexts)
# archived and withdrawn are reachable from any state
_FORWARD_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["baseline_in_progress", "archived", "withdrawn"],
    "baseline_in_progress": ["baseline_complete", "archived", "withdrawn"],
    "baseline_complete": ["gumi_seed_generated", "archived", "withdrawn"],
    "gumi_seed_generated": ["gumi_seed_reviewed", "archived", "withdrawn"],
    "gumi_seed_reviewed": ["hermes_profile_provisioned", "archived", "withdrawn"],
    "hermes_profile_provisioned": ["intro_composed", "archived", "withdrawn"],
    "intro_composed": ["intro_sent", "archived", "withdrawn"],
    "intro_sent": ["active", "archived", "withdrawn"],
    "active": ["archived", "withdrawn"],
    "archived": ["withdrawn"],
    "withdrawn": [],
}

SUBJECT_FILES = [
    "subject_profile.json",
    "consent_record.json",
    "baseline_user_profile.json",
    "gumi_seed_profile.json",
    "gumi_background_profile.json",
    "gumi_sweet_spot_config.json",
    "gumi_intro_message.json",
    "bootstrap_session.jsonl",
    "profile_edit_log.jsonl",
]

SUBJECT_DIRS = ["provenance", "exports"]

GUMI_SUBJECT_OUTPUTS = [
    "gumi_background_profile.json",
    "gumi_seed_profile.json",
    "gumi_sweet_spot_config.json",
    "gumi_world.md",
    "gumi_relationship_policy.md",
    "gumi_social_graph.json",
    "gumi_visual_canon.json",
    "gumi_music_canon.json",
    "gumi_daily_rhythm.json",
]

HERMES_PROFILE_OUTPUTS = [
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "config.yaml",
    ".env",
    "workspace/gumi/background.json",
    "workspace/gumi/world.md",
    "workspace/gumi/relationship_policy.md",
    "workspace/gumi/visual_canon.json",
    "workspace/gumi/voice_canon.json",
    "workspace/gumi/lyria_canon.json",
    "workspace/gumi/media_policy.json",
]

# Fields to redact on export
_REDACTED_FIELDS = {"hermes_home", "relic_subject_home"}
_TELEGRAM_BOT_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_values(path: Path, values: dict[str, str]) -> None:
    existing = _parse_env_text(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n",
        encoding="utf-8",
    )


def _render_simple_yaml(data: dict[str, Any]) -> str:
    def render_value(value: Any, indent: int = 0) -> list[str]:
        pad = " " * indent
        if isinstance(value, dict):
            lines: list[str] = []
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    lines.append(f"{pad}{key}:")
                    lines.extend(render_value(item, indent + 2))
                else:
                    lines.append(f"{pad}{key}: {item}")
            return lines
        if isinstance(value, list):
            lines = []
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{pad}-")
                    lines.extend(render_value(item, indent + 2))
                else:
                    lines.append(f"{pad}- {item}")
            return lines
        return [f"{pad}{value}"]

    return "\n".join(render_value(data)) + "\n"


@dataclass
class SubjectProfile:
    subject_id: str
    experiment_id: str
    status: str
    hermes_profile_name: str
    hermes_home: Path
    relic_subject_home: Path
    profile_version: int
    created_at: str
    updated_at: str
    # WIRE02: Runtime wiring fields
    session_key_hash: str = ""
    delivery_enabled: bool = False
    delivery_allowlist: list = field(default_factory=list)
    runtime_status: str = "pending"
    resume_reconciliation_state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hermes_home"] = str(self.hermes_home)
        d["relic_subject_home"] = str(self.relic_subject_home)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SubjectProfile":
        return cls(
            subject_id=data["subject_id"],
            experiment_id=data["experiment_id"],
            status=data["status"],
            hermes_profile_name=data["hermes_profile_name"],
            hermes_home=Path(data["hermes_home"]),
            relic_subject_home=Path(data["relic_subject_home"]),
            profile_version=data.get("profile_version", 1),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            session_key_hash=data.get("session_key_hash", ""),
            delivery_enabled=data.get("delivery_enabled", False),
            delivery_allowlist=data.get("delivery_allowlist", []),
            runtime_status=data.get("runtime_status", "pending"),
            resume_reconciliation_state=data.get("resume_reconciliation_state", {}),
        )


@dataclass
class ProfileEditEvent:
    event_type: str = "profile_edit_event"
    subject_id: str = ""
    profile_version_before: int = 0
    profile_version_after: int = 0
    edited_fields: list[str] = field(default_factory=list)
    edit_mode: str = "manual"  # "manual" | "tui" | "api"
    researcher_id: str = ""
    requires_intro_regeneration: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileEditEvent":
        return cls(**data)


@dataclass
class DeliveryPolicy:
    subject_id: str
    contact_channel: str
    telegram_user_id_hash: str
    telegram_user_id_display: str
    telegram_bot_token_env: str
    delivery_enabled: bool
    quiet_hours: str
    maximum_contact_frequency: str
    delivery_windows: list  # [{"start": "HH:MM", "end": "HH:MM"}, ...]
    timezone: str  # IANA timezone string, e.g. "Europe/Rome"
    consent_for_active_elicitation: bool
    consent_for_generated_images: bool
    consent_for_generated_audio: bool
    consent_for_generated_music: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MediaCanon:
    subject_id: str
    visual_reference_set_id: str
    visual_taste: dict[str, Any]
    voice_tone: dict[str, Any]
    lyria_tone: dict[str, Any]
    media_policy: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProfileRegistry:
    def __init__(
        self,
        relic_home: Optional[Path] = None,
        hermes_profiles_home: Optional[Path] = None,
    ) -> None:
        if relic_home is None:
            relic_home = get_relic_home()
        if hermes_profiles_home is None:
            env_home = os.environ.get("HERMES_PROFILES_HOME")
            hermes_profiles_home = (
                Path(env_home) if env_home else Path.home() / ".hermes" / "profiles"
            )
        self.relic_home = relic_home
        self.hermes_profiles_home = hermes_profiles_home
        self.subjects_dir = relic_home / "subjects"
        self.subjects_dir.mkdir(parents=True, exist_ok=True)

    def _subject_dir(self, subject_id: str) -> Path:
        return self.subjects_dir / subject_id

    def _profile_path(self, subject_id: str) -> Path:
        return self._subject_dir(subject_id) / "subject_profile.json"

    def _edit_log_path(self, subject_id: str) -> Path:
        return self._subject_dir(subject_id) / "profile_edit_log.jsonl"

    def _load_profile(self, subject_id: str) -> Optional[SubjectProfile]:
        path = self._profile_path(subject_id)
        if not path.exists():
            return None
        with open(path) as f:
            return SubjectProfile.from_dict(json.load(f))

    def _save_profile(self, profile: SubjectProfile) -> None:
        path = self._profile_path(profile.subject_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(path, profile.to_dict())

    def list_subjects(self) -> list[SubjectProfile]:
        results = []
        if not self.subjects_dir.exists():
            return results
        for entry in sorted(self.subjects_dir.iterdir()):
            if entry.is_dir():
                p = self._load_profile(entry.name)
                if p is not None:
                    results.append(p)
        return results

    def get_subject(self, subject_id: str) -> Optional[SubjectProfile]:
        return self._load_profile(subject_id)

    def create_subject(self, subject_id: str, experiment_id: str) -> SubjectProfile:
        if self._profile_path(subject_id).exists():
            raise ValueError(f"Subject '{subject_id}' already exists. Will not overwrite.")

        hermes_profile_name = f"gumi-{subject_id}"
        relic_subject_home = self._subject_dir(subject_id)
        hermes_home = self.hermes_profiles_home / hermes_profile_name

        now = _now_iso()

        # WIRE02: Derive session_key_hash scoped to this subject
        # gumi_instance_id and hermes_profile_id use subject_id as default scope
        session_key_hash = ""
        session_key_derivation_failed = False
        try:
            session_key_hash = HermesSessionKey.derive(
                subject_id=subject_id,
                gumi_instance_id=subject_id,
                hermes_profile_id=hermes_profile_name,
            )
        except ValueError:
            # Fail closed if session key derivation fails
            session_key_derivation_failed = True

        profile = SubjectProfile(
            subject_id=subject_id,
            experiment_id=experiment_id,
            status="draft",
            hermes_profile_name=hermes_profile_name,
            hermes_home=hermes_home,
            relic_subject_home=relic_subject_home,
            profile_version=1,
            created_at=now,
            updated_at=now,
            # WIRE02: Runtime wiring fields
            session_key_hash=session_key_hash,
            delivery_enabled=False,  # Not enabled until delivery is configured
            delivery_allowlist=[],  # Empty allowlist at creation
            runtime_status="pending",
            resume_reconciliation_state={},
        )

        # Create directory structure
        relic_subject_home.mkdir(parents=True, exist_ok=True)
        for d in SUBJECT_DIRS:
            (relic_subject_home / d).mkdir(exist_ok=True)
        self._prepare_hermes_profile(profile)

        # WIRE02: Runtime provisioning with fail-closed behavior
        try:
            # Fail closed if session key derivation failed
            if session_key_derivation_failed:
                raise ValueError("session_key_hash derivation failed - subject_id may be empty")

            # Initialize Shared Continuity scopes for this subject
            continuity_service = get_continuity_service()
            continuity_service.pause(
                subject_id=subject_id,
                scope_name="global",
                gumi_instance_id=subject_id,
                hermes_profile_id=hermes_profile_name,
            )
            # Immediately resume to initialize the scope as active
            continuity_service.resume(
                subject_id=subject_id,
                scope_name="global",
                gumi_instance_id=subject_id,
                hermes_profile_id=hermes_profile_name,
            )

            # Call provision_no_agent_cron for this subject (dry_run=True by default)
            provision_result = provision_no_agent_cron(
                subject_id=subject_id,
                gumi_instance_id=subject_id,
                hermes_profile_id=hermes_profile_name,
                dry_run=True,
                script_path=hermes_home / "scripts" / "relic_no_agent_decision.sh",
            )

            # Initialize resume reconciliation state
            from relic.hermes_runtime import SessionResumeState
            resume_state = SessionResumeState(
                subject_id=subject_id,
                gumi_instance_id=subject_id,
                hermes_profile_id=hermes_profile_name,
                session_key_hash=session_key_hash,
                platform_allowlist_valid=True,
                delivery_enabled=False,
                continuity_marker_active=True,
                continuity_scope_paused=False,
                followup_attempt_count=0,
                safety_review_required=False,
            )
            profile.resume_reconciliation_state = {
                "initialized": True,
                "session_key_hash": session_key_hash,
                "gumi_instance_id": subject_id,
                "hermes_profile_id": hermes_profile_name,
            }

            # All runtime wiring succeeded
            profile.runtime_status = "configured"

            # Write session key hash to subject home (hash only, not raw key)
            self._write_runtime_artifact(
                profile,
                ".session_key_hash",
                {
                    "session_key_hash": session_key_hash,
                    "hash_algorithm": "sha256",
                    "created_at": now,
                },
            )

            # Write delivery allowlist (empty at creation)
            self._write_runtime_artifact(
                profile,
                "delivery_allowlist.json",
                {"allowlist": [], "subject_id": subject_id, "created_at": now},
            )

            # Write runtime status artifact
            self._write_runtime_artifact(
                profile,
                "runtime_status.json",
                {
                    "runtime_status": "configured",
                    "session_key_hash": session_key_hash,
                    "delivery_enabled": False,
                    "provision_no_agent_cron": provision_result,
                    "continuity_scope_initialized": True,
                    "resume_reconciliation_initialized": True,
                    "created_at": now,
                },
            )

        except Exception as exc:
            # Fail closed: mark incomplete, disable delivery
            profile.runtime_status = "incomplete"
            profile.delivery_enabled = False
            profile.session_key_hash = session_key_hash if session_key_hash else ""

            # Write failure artifact
            self._write_runtime_artifact(
                profile,
                "runtime_status.json",
                {
                    "runtime_status": "incomplete",
                    "failure_reason": str(exc),
                    "delivery_enabled": False,
                    "created_at": now,
                },
            )

            # Emit setup_failed event (audit log)
            self._emit_setup_failed_event(profile, str(exc))

        self._save_profile(profile)
        return profile

    def _write_runtime_artifact(self, profile: SubjectProfile, filename: str, data: dict) -> None:
        """Write a runtime artifact to the subject's home directory."""
        artifact_path = profile.relic_subject_home / filename
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(artifact_path, data)

    def _emit_setup_failed_event(self, profile: SubjectProfile, reason: str) -> None:
        """Emit a setup_failed event for audit purposes."""
        event_path = profile.relic_subject_home / "setup_failed.jsonl"
        event = {
            "event_type": "setup_failed",
            "subject_id": profile.subject_id,
            "failure_reason": reason,
            "runtime_status": "incomplete",
            "delivery_enabled": False,
            "timestamp": _now_iso(),
        }
        with open(event_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _prepare_hermes_profile(self, profile: SubjectProfile) -> None:
        profile.hermes_home.mkdir(parents=True, exist_ok=True)
        placeholders = {
            "SOUL.md": (
                "# Gumi\n\n"
                "Private persona seed for this subject-specific Gumi profile.\n"
                "This file must not contain project workflow instructions or raw private user facts.\n"
            ),
            "USER.md": (
                "# User Snapshot\n\n"
                "Initialized by Relic profile bootstrap. Keep subject data governed by Relic.\n"
            ),
            "MEMORY.md": (
                "# Memory Snapshot\n\n"
                "Initialized empty. Do not store raw chat logs or unredacted private data here.\n"
            ),
        }
        for filename, content in placeholders.items():
            path = profile.hermes_home / filename
            if not path.exists():
                path.write_text(content)

    def _load_required_subject(self, subject_id: str) -> SubjectProfile:
        profile = self._load_profile(subject_id)
        if profile is None:
            raise KeyError(f"Subject '{subject_id}' not found.")
        return profile

    def _transition_if_current(
        self,
        profile: SubjectProfile,
        expected_status: str,
        next_status: str,
    ) -> SubjectProfile:
        if profile.status != expected_status:
            return profile
        return self.update_status(profile.subject_id, next_status)

    def _subject_profile_input(self, profile: SubjectProfile) -> dict[str, Any]:
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        subject_data = profile.to_dict()
        if baseline_path.exists():
            subject_data.update(_read_json(baseline_path))
        return subject_data

    def _delivery_policy_path(self, subject_id: str) -> Path:
        return self._subject_dir(subject_id) / "delivery_policy.json"

    def _media_canon_paths(self, subject_id: str) -> dict[str, Path]:
        subject_home = self._subject_dir(subject_id)
        return {
            "visual": subject_home / "gumi_visual_canon.json",
            "voice": subject_home / "gumi_voice_canon.json",
            "lyria": subject_home / "gumi_lyria_canon.json",
            "policy": subject_home / "gumi_media_policy.json",
        }

    def _hermes_workspace_gumi_dir(self, profile: SubjectProfile) -> Path:
        return profile.hermes_home / "workspace" / "gumi"

    def configure_telegram_delivery(
        self,
        subject_id: str,
        telegram_bot_token_env: str,
        telegram_user_id: str,
        contact_channel: str = "telegram",
        quiet_hours: str = "22:00-08:00",
        maximum_contact_frequency: str = "2/day",
        delivery_windows: list | None = None,
        timezone: str = "Europe/Rome",
        consent_for_active_elicitation: bool = False,
        consent_for_generated_images: bool = False,
        consent_for_generated_audio: bool = False,
        consent_for_generated_music: bool = False,
    ) -> tuple[SubjectProfile, DeliveryPolicy]:
        profile = self._load_required_subject(subject_id)
        if profile.status in {"archived", "withdrawn"}:
            raise ValueError("Cannot configure delivery for archived or withdrawn subjects.")
        if contact_channel != "telegram":
            raise ValueError("Only telegram delivery is supported in this configuration path.")
        if not _TELEGRAM_BOT_ENV_RE.match(telegram_bot_token_env):
            raise ValueError("Invalid Telegram bot token env name.")
        self._ensure_unique_telegram_delivery(
            profile=profile,
            telegram_bot_token_env=telegram_bot_token_env,
            telegram_user_id=telegram_user_id,
        )

        _default_windows = [
            {"start": "09:00", "end": "11:00"},
            {"start": "19:00", "end": "21:00"},
        ]
        policy = DeliveryPolicy(
            subject_id=subject_id,
            contact_channel=contact_channel,
            telegram_user_id_hash=_hash_identifier(telegram_user_id),
            telegram_user_id_display=f"telegram:{telegram_user_id[-4:]}" if len(telegram_user_id) >= 4 else "telegram:****",
            telegram_bot_token_env=telegram_bot_token_env,
            delivery_enabled=True,
            quiet_hours=quiet_hours,
            maximum_contact_frequency=maximum_contact_frequency,
            delivery_windows=delivery_windows if delivery_windows is not None else _default_windows,
            timezone=timezone,
            consent_for_active_elicitation=consent_for_active_elicitation,
            consent_for_generated_images=consent_for_generated_images,
            consent_for_generated_audio=consent_for_generated_audio,
            consent_for_generated_music=consent_for_generated_music,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )

        self._write_delivery_env(profile, telegram_bot_token_env, telegram_user_id)
        _write_json(self._delivery_policy_path(subject_id), policy.to_dict())

        # Propagate consent flags to media_policy.json so the media dispatcher can
        # gate generation without re-reading delivery_policy.json.
        media_policy_path = self._hermes_workspace_gumi_dir(profile) / "media_policy.json"
        if media_policy_path.exists():
            media_policy = _read_json(media_policy_path)
            media_policy["image_generation_enabled"] = consent_for_generated_images
            media_policy["audio_generation_enabled"] = consent_for_generated_audio
            media_policy["music_generation_enabled"] = consent_for_generated_music
            _write_json(media_policy_path, media_policy)

        now = _now_iso()
        allowlist_entry = {
            "subject_id": subject_id,
            "platform": "telegram",
            "enabled": True,
            "target_hash": policy.telegram_user_id_hash,
            "target_display": policy.telegram_user_id_display,
            "created_at": now,
            "updated_at": now,
        }
        register_allowlist_entry(allowlist_entry)
        profile.delivery_enabled = True
        profile.delivery_allowlist = [allowlist_entry]
        profile.updated_at = now
        self._save_profile(profile)
        _write_json(
            profile.relic_subject_home / "delivery_allowlist.json",
            {
                "subject_id": subject_id,
                "allowlist": [allowlist_entry],
                "updated_at": now,
            },
        )
        return profile, policy

    def _ensure_unique_telegram_delivery(
        self,
        profile: SubjectProfile,
        telegram_bot_token_env: str,
        telegram_user_id: str,
    ) -> None:
        requested_user_hash = _hash_identifier(telegram_user_id)
        requested_token = os.environ.get(telegram_bot_token_env)
        requested_token_hash = _hash_identifier(requested_token) if requested_token else ""
        for other in self.list_subjects():
            if other.subject_id == profile.subject_id:
                continue
            policy_path = self._delivery_policy_path(other.subject_id)
            if not policy_path.exists():
                continue
            other_policy = _read_json(policy_path)
            if other_policy.get("contact_channel") != "telegram":
                continue
            if other_policy.get("telegram_user_id_hash") == requested_user_hash:
                raise ValueError(f"Telegram user id is already assigned to subject '{other.subject_id}'.")
            if other_policy.get("telegram_bot_token_env") == telegram_bot_token_env:
                raise ValueError(f"Telegram bot token env is already assigned to subject '{other.subject_id}'.")
            if requested_token_hash:
                other_env = self._load_hermes_env(other)
                other_token = other_env.get("TELEGRAM_BOT_TOKEN")
                if other_token and _hash_identifier(other_token) == requested_token_hash:
                    raise ValueError(f"Telegram bot token is already assigned to subject '{other.subject_id}'.")

    def _write_delivery_env(self, profile: SubjectProfile, bot_token_env: str, telegram_user_id: str) -> None:
        env_path = profile.hermes_home / ".env"
        values = {
            "TELEGRAM_ALLOWED_USERS": telegram_user_id,
            "TELEGRAM_HOME_CHANNEL": f"telegram:{telegram_user_id}",
            "GUMI_TELEGRAM_BOT_TOKEN_ENV": bot_token_env,
            "GUMI_DELIVERY_CHANNEL": "telegram",
        }
        token = os.environ.get(bot_token_env)
        if token:
            values["TELEGRAM_BOT_TOKEN"] = token
        _write_env_values(env_path, values)

    def _load_hermes_env(self, profile: SubjectProfile) -> dict[str, str]:
        env_path = profile.hermes_home / ".env"
        if not env_path.exists():
            return {}
        return _parse_env_text(env_path.read_text(encoding="utf-8"))

    def _telegram_target(self, profile: SubjectProfile) -> str | None:
        env_values = self._load_hermes_env(profile)
        home_channel = env_values.get("TELEGRAM_HOME_CHANNEL", "")
        if home_channel.startswith("telegram:"):
            return home_channel
        allowed = env_values.get("TELEGRAM_ALLOWED_USERS", "")
        if allowed:
            first_allowed = allowed.split(",")[0].strip()
            if first_allowed:
                return f"telegram:{first_allowed}"
        return None

    def generate_gumi_media_canon(
        self,
        subject_id: str,
        seed: int | None = None,
    ) -> tuple[SubjectProfile, MediaCanon, dict[str, Path]]:
        profile = self._load_required_subject(subject_id)
        background_path = profile.relic_subject_home / "gumi_background_profile.json"
        if not background_path.exists():
            raise FileNotFoundError("Missing gumi_background_profile.json.")
        background = _read_json(background_path)
        domains = background.get("domains", {})
        passions = domains.get("passions", {})
        visual = {
            "visual_reference_set_id": f"gumi_canon_{seed or 1}",
            "style": "quiet naturalism",
            "palette": ["desaturated teal", "warm gray", "soft amber"],
            "motifs": ["indoor light", "handmade objects", "small rituals"],
            "negative_motifs": ["glow blobs", "stock portrait", "generic neon"],
            "prompt_constraints": "describe atmosphere and composition; do not invent real image outputs",
        }
        voice = {
            "voice_profile": "warm, concise, slightly intimate",
            "pace": "moderate",
            "timbre": "clear low-mid",
            "register": "everyday conversational",
            "avoid": ["grandiose romance", "dependency claims", "clinical tone"],
        }
        lyria = {
            "music_profile": "lyric-light, reflective, non-derivative",
            "mood_palette": ["late evening", "soft motion", "quiet focus"],
            "instrumentation": ["light percussion", "pads", "distant piano"],
            "forbidden": ["song lyrics", "artist imitation", "copyrighted melody mimicry"],
            "references": passions.get("music_preferences", []),
        }
        policy = {
            "provider_required": False,
            "image_generation_enabled": False,
            "audio_generation_enabled": False,
            "music_generation_enabled": False,
            "all_outputs_local_only": True,
            "consent_required": True,
        }
        canon = MediaCanon(
            subject_id=subject_id,
            visual_reference_set_id=visual["visual_reference_set_id"],
            visual_taste=visual,
            voice_tone=voice,
            lyria_tone=lyria,
            media_policy=policy,
            created_at=_now_iso(),
        )
        paths = self._media_canon_paths(subject_id)
        payload = canon.to_dict()
        _write_json(paths["visual"], visual)
        _write_json(paths["voice"], voice)
        _write_json(paths["lyria"], lyria)
        _write_json(paths["policy"], policy)
        workspace = self._hermes_workspace_gumi_dir(profile)
        workspace.mkdir(parents=True, exist_ok=True)
        _write_json(workspace / "visual_canon.json", visual)
        _write_json(workspace / "voice_canon.json", voice)
        _write_json(workspace / "lyria_canon.json", lyria)
        _write_json(workspace / "media_policy.json", policy)
        # C3: Add voice_id to voice dict
        try:
            from relic.gumi_plugin.tts import select_voice_for_canon
            voice["voice_id"] = select_voice_for_canon(background)
        except Exception:
            voice["voice_id"] = "Kore"  # fallback
        _write_json(paths["voice"], voice)
        _write_json(workspace / "voice_canon.json", voice)

        # C1: Generate AVATAR_SPEC.md via Ollama narrator (fallback to template)
        try:
            from relic.gumi.llm_narrator import GumiBuildContext, OllamaNarrator
            import os as _os
            ollama_endpoint = _os.environ.get("RELIC_OLLAMA_ENDPOINT", "http://localhost:11434/v1")
            ollama_model = _os.environ.get("RELIC_OLLAMA_MODEL", "qwen3:latest")
            _narrator = OllamaNarrator(endpoint=ollama_endpoint, model=ollama_model)
            _ctx = GumiBuildContext.from_background_and_personalization(
                agent_name=background.get("display_name", subject_id),
                background=background,
            )
            if _narrator.is_available():
                avatar_spec = _narrator.generate_avatar_spec_md(_ctx)
            else:
                avatar_spec = _narrator.fallback_avatar_spec_md(_ctx)
        except Exception:
            avatar_spec = (
                f"{background.get('display_name', subject_id)}. "
                f"Visual style: quiet naturalism, desaturated palette, natural light. "
                f"No artificial glow or stock portrait aesthetics."
            )
        (profile.hermes_home / "AVATAR_SPEC.md").write_text(avatar_spec, encoding="utf-8")

        # C1: Generate PHOTO_MODES.md
        photo_modes = """# Photo Modes for Gumi

Eight visual modes for consistent photography:

1. **close_selfie**: Tight frame on face and shoulders, natural expression, soft side light
2. **mirror_corner_selfie**: Bathroom mirror shot, slightly candid, warm reflected light
3. **bed_soft_frame**: Morning bed scene, soft sheets, sleepy atmosphere, natural window light
4. **desk_process_shot**: Workspace detail with hands or small objects, focused, afternoon light
5. **window_or_balcony_portrait**: Subject with window/balcony backdrop, soft bokeh, natural outdoor light
6. **room_detail**: Environmental shot showing room context, objects, natural composition
7. **neighborhood_ambient**: Outdoor neighborhood context, casual, real locations
8. **idol_in_progress_frame**: Late night scene, intimate atmosphere, artificial lamp light
"""
        (profile.hermes_home / "PHOTO_MODES.md").write_text(photo_modes, encoding="utf-8")

        # C2: Generate anchor image if GEMINI_API_KEY available
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from relic.gumi_plugin.image_gen import (
                    build_image_prompt, generate_image, collect_reference_images, load_avatar_spec
                )
                avatar_text = load_avatar_spec(profile.hermes_home)
                prompt = build_image_prompt(avatar_text, visual, "close_selfie")
                anchor_path = profile.relic_subject_home / "gumi_visual_anchor.jpg"
                generate_image(prompt, [], anchor_path, gemini_key)
                # Copy to Visual_Identity/
                vi_dir = profile.relic_subject_home / "Visual_Identity"
                vi_dir.mkdir(exist_ok=True)
                shutil.copy(anchor_path, vi_dir / "gumi_anchor_001.jpg")
                manifest = {"entries": [{"file": "gumi_anchor_001.jpg", "use_for_identity_anchor": True, "strength": 1.0}]}
                (vi_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
                # Update visual_canon with anchor_hash
                anchor_hash = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
                visual["anchor_hash"] = anchor_hash
                visual["seed_prompt"] = prompt
                _write_json(paths["visual"], visual)
            except Exception:
                pass  # Skip image generation on error

        _write_json(profile.relic_subject_home / "provenance" / "gumi_media_canon.json", payload)
        return profile, canon, paths

    def provision_subject_cron_specs(
        self,
        subject_id: str,
        families: list[str],
        dry_run: bool = True,
    ) -> tuple[SubjectProfile, dict[str, Path]]:
        profile = self._load_required_subject(subject_id)
        cron_dir = profile.hermes_home / "cron"
        cron_dir.mkdir(parents=True, exist_ok=True)
        workspace_cron = profile.hermes_home / "workspace" / "gumi" / "cron"
        workspace_cron.mkdir(parents=True, exist_ok=True)
        manifest = {
            "subject_id": subject_id,
            "hermes_profile_name": profile.hermes_profile_name,
            "families": families,
            "dry_run": dry_run,
            "hermes_native": True,
            "install_strategy": "hermes cron create",
            "notes": "Use HERMES_HOME for this private profile; Hermes delivers final cron responses to target.",
            "install_commands": [],
            "apply_results": [],
            "created_at": _now_iso(),
        }
        paths: dict[str, Path] = {}
        jobs_to_apply: list[dict[str, Any]] = []
        if "maintenance" in families:
            data = {
                "version": "1.0",
                "family": "maintenance",
                "target": "local",
                "success_contract": "[SILENT]",
                "jobs": [
                    {
                        "id": f"{subject_id}_world_state_compaction",
                        "task": "world_state_compaction",
                        "schedule": "0 3 * * *",
                        "target": "local",
                        "dry_run_default": True,
                        "output": str(workspace_cron / "world_state_compaction_report.json"),
                        "prompt_contract": "Update bounded local continuity state only; return [SILENT] on success and a short diagnostic on failure.",
                    },
                    {
                        "id": f"{subject_id}_continuity_candidate_review",
                        "task": "continuity_candidate_review",
                        "schedule": "0 4 * * *",
                        "target": "local",
                        "dry_run_default": True,
                        "output": str(workspace_cron / "continuity_candidate_review_report.json"),
                        "prompt_contract": "Review local continuity candidates only; return [SILENT] when there is no actionable drift.",
                    },
                    {
                        "id": f"{subject_id}_memory_exposure_log_rollup",
                        "task": "memory_exposure_log_rollup",
                        "schedule": "0 5 * * 0",
                        "target": "local",
                        "dry_run_default": True,
                        "output": str(workspace_cron / "memory_exposure_log_rollup_report.json"),
                        "prompt_contract": "Aggregate and redact memory exposure events for this subject only; write rollup to output path; return [SILENT] on success.",
                    },
                    {
                        "id": f"{subject_id}_provider_eval_metric_rollup",
                        "task": "provider_eval_metric_rollup",
                        "schedule": "0 6 * * 0",
                        "target": "local",
                        "dry_run_default": True,
                        "output": str(workspace_cron / "provider_eval_metric_rollup_report.json"),
                        "prompt_contract": "Aggregate provider evaluation metrics for this subject only; write rollup to output path; return [SILENT] on success.",
                    },
                ],
            }
            path = cron_dir / "maintenance.yaml"
            path.write_text(_render_simple_yaml(data), encoding="utf-8")
            paths["maintenance"] = path
            jobs_to_apply.extend(data["jobs"])
        if "initiative" in families:
            policy_path = self._delivery_policy_path(subject_id)
            if not policy_path.exists():
                raise ValueError("Initiative cron requires delivery_policy.json.")
            target = self._telegram_target(profile)
            if target is None:
                raise ValueError("Initiative cron requires TELEGRAM_ALLOWED_USERS or TELEGRAM_HOME_CHANNEL in Hermes .env.")
            checkin_script = f"{subject_id}/relic_checkin_decision.sh"
            data = {
                "version": "1.0",
                "family": "initiative",
                "target": target,
                "success_contract": "Hermes delivers the final response to the target; do not perform a second delivery action.",
                "jobs": [
                    {
                        "id": f"{subject_id}_checkin_gate",
                        "task": "gumi_checkin_gate",
                        "schedule": "*/30 * * * *",
                        "target": "local",
                        "no_agent": True,
                        "script": checkin_script,
                        "dry_run_default": True,
                    },
                    {
                        "id": f"{subject_id}_checkin_message",
                        "task": "gumi_checkin_message",
                        "schedule": "*/30 * * * *",
                        "target": target,
                        "script": checkin_script,
                        "dry_run_default": True,
                        "output": str(workspace_cron / "checkin_decision_log.jsonl"),
                        "prompt_contract": "The gate script result above shows whether contact is warranted. If it is empty or indicates BLOCKED/NO_REPLY, respond exactly [SILENT]. Otherwise write a natural message as Gumi.",
                    },
                ],
            }
            path = cron_dir / "initiative.yaml"
            path.write_text(_render_simple_yaml(data), encoding="utf-8")
            paths["initiative"] = path
            jobs_to_apply.extend(data["jobs"])
        # T5: gumi_memory_sync — no-agent script that syncs cron sessions → MEMORY.md
        memory_sync_script = f"{subject_id}/relic_memory_sync.sh"
        memory_sync_job = {
            "id": f"{subject_id}_memory_sync",
            "task": "gumi_memory_sync",
            "schedule": "2-59/30 * * * *",
            "target": "local",
            "no_agent": True,
            "script": memory_sync_script,
            "dry_run_default": False,
        }
        jobs_to_apply.append(memory_sync_job)

        # T6: One-shot backfill — seed watermark so first tick skips historical sessions.
        from relic.gumi_plugin.memory_sync import sync as memory_sync_sync
        if not dry_run:
            memory_sync_result = memory_sync_sync(profile.hermes_home)
            manifest["memory_sync_backfill"] = memory_sync_result

        if "media" in families:
            # Media is injected probabilistically inside checkin_message (Phase D).
            # No standalone cron jobs needed; record the family as provisioned.
            data = {
                "version": "1.0",
                "family": "media",
                "note": "Media delivered inline in checkin_message via probabilistic dispatcher.",
                "jobs": [],
            }
            path = cron_dir / "media.yaml"
            path.write_text(_render_simple_yaml(data), encoding="utf-8")
            paths["media"] = path
        manifest["install_commands"] = [
            self._render_hermes_cron_create_command(profile, job) for job in jobs_to_apply
        ]
        if not dry_run:
            manifest["apply_results"] = self._apply_hermes_cron_jobs(profile, jobs_to_apply)
        _write_json(cron_dir / "install_manifest.json", manifest)
        _write_json(profile.relic_subject_home / "gumi_cron_manifest.json", manifest)
        return profile, paths

    def _cron_prompt_for_job(self, job: dict[str, Any]) -> str:
        task = job["task"]
        output = job.get("output", "")
        if task == "gumi_checkin_gate":
            return ""
        if task == "gumi_memory_sync":
            return ""
        if task == "gumi_checkin_message":
            return (
                "Il gate mostra DELIVER con tipo e ora. Comportati così:\n"
                "\n"
                "- tipo: text → scrivi un messaggio breve naturale come Gumi, max 2 frasi, in italiano. "
                "Non ripetere argomenti già usati di recente. Includi una domanda genuina solo se naturale.\n"
                "\n"
                "- tipo: voice → scrivi SOLO il testo del messaggio vocale (max 2 frasi, tono parlato, in italiano). "
                "Il sistema lo converte in audio automaticamente.\n"
                "\n"
                "- tipo: image → scrivi esattamente in questo formato (due righe, nient'altro):\n"
                "  caption: <1 frase in italiano, stile 'Oggi ho fatto questo'>\n"
                "  image_prompt: <descrizione fotorealistica dettagliata in inglese per generare una foto di Gumi: "
                "aspetto, abbigliamento casual, ambiente, luce naturale, stile candid. Max 100 parole.>\n"
                "\n"
                "- tipo: music → scrivi un prompt completo per Lyria 3 in inglese, includendo:\n"
                "  singer profile (es. 'Female mezzo-soprano, warm timbre'), stile musicale,\n"
                "  [Verse] con 2 righe di testo in inglese (max 10 parole per riga),\n"
                "  [Chorus] con 2 righe in inglese. Scrivi SOLO il prompt, nient'altro.\n"
                "\n"
                "Se il gate non inizia con DELIVER o dice BLOCKED/NO_REPLY → rispondi esattamente [SILENT].\n"
                "L'ora calibra il tono (mattina/sera) ma non menzionarla esplicitamente.\n"
                + (f"Aggiungi un record decisionale redatto a {output}." if output else "")
            )
        if task in {"world_state_compaction", "continuity_candidate_review"}:
            return (
                f"Run {task} for this subject's private Gumi workspace. Mutate only bounded local state. "
                f"Write the audit result to {output}. On success respond exactly [SILENT]; on failure return a short diagnostic."
            )
        if task == "memory_exposure_log_rollup":
            return (
                f"Aggregate and redact memory exposure events for this subject only. "
                f"Do not access raw chat logs, MEMORY.md, or USER.md. "
                f"Write the rollup to {output}. On success respond exactly [SILENT]; on failure return a short diagnostic."
            )
        if task == "provider_eval_metric_rollup":
            return (
                f"Aggregate provider evaluation metrics for this subject only. "
                f"Do not call any provider API or mutate any profile file. "
                f"Write the rollup to {output}. On success respond exactly [SILENT]; on failure return a short diagnostic."
            )
        return (
            f"Run {task} for this subject's private Gumi media canon. Do not call media providers unless "
            f"the local media policy explicitly enables them. Write the audit result to {output}. "
            "On success respond exactly [SILENT]; on failure return a short diagnostic."
        )

    def _render_hermes_cron_create_command(self, profile: SubjectProfile, job: dict[str, Any]) -> str:
        parts = [f"HERMES_HOME={profile.hermes_home}", "hermes", "cron", "create"]
        if job.get("no_agent"):
            parts.append("--no-agent")
        if job.get("script"):
            parts += ["--script", job["script"]]
        parts.append(json.dumps(job["schedule"]))
        prompt = self._cron_prompt_for_job(job)
        if prompt:
            parts.append(json.dumps(prompt))
        parts += ["--name", json.dumps(job["id"])]
        # Skip --deliver for local no-agent jobs (memory_sync etc.)
        if not (job.get("no_agent") and job.get("target") == "local"):
            parts += ["--deliver", json.dumps(job["target"])]
        return " ".join(parts)

    def _apply_hermes_cron_jobs(
        self,
        profile: SubjectProfile,
        jobs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        hermes_bin = shutil.which("hermes")
        if hermes_bin is None:
            raise FileNotFoundError("hermes command not found.")
        env_values = self._load_hermes_env(profile)
        run_env = os.environ.copy()
        run_env.update(env_values)
        run_env["HERMES_HOME"] = str(profile.hermes_home)
        results: list[dict[str, Any]] = []
        for job in jobs:
            cmd = [hermes_bin, "cron", "create"]
            if job.get("no_agent"):
                cmd.append("--no-agent")
            if job.get("script"):
                cmd += ["--script", job["script"]]
            cmd.append(job["schedule"])
            prompt = self._cron_prompt_for_job(job)
            if prompt:
                cmd.append(prompt)
            cmd += ["--name", job["id"]]
            # Skip --deliver for local no-agent jobs (memory_sync etc.)
            if not (job.get("no_agent") and job.get("target") == "local"):
                cmd += ["--deliver", job["target"]]
            result = subprocess.run(
                cmd,
                env=run_env,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            entry = {
                "job_id": job["id"],
                "returncode": result.returncode,
                "stdout": result.stdout.strip()[:500],
                "stderr": result.stderr.strip()[:500],
            }
            results.append(entry)
            if result.returncode != 0:
                raise RuntimeError(f"Hermes cron create failed for {job['id']} with exit code {result.returncode}.")
        return results

    def _check_delivery_gate(self, subject_id: str, platform: str) -> tuple[bool, str | None]:
        """Check DeliveryGate for the given platform. Returns (allowed, reason)."""
        from relic.hermes_runtime import DeliveryGate, DeliveryGateDecision, get_allowlist_entry

        profile = self._load_required_subject(subject_id)

        # Check allowlist entry — fall back to disk if in-memory store is empty (cross-process)
        entry = get_allowlist_entry(subject_id, platform)
        if entry is None:
            allowlist_path = self._subject_dir(subject_id) / "delivery_allowlist.json"
            if allowlist_path.exists():
                from relic.hermes_runtime import register_allowlist_entry
                allowlist_data = _read_json(allowlist_path)
                for disk_entry in allowlist_data.get("allowlist", []):
                    if disk_entry.get("subject_id") == subject_id:
                        register_allowlist_entry(disk_entry)
                entry = get_allowlist_entry(subject_id, platform)
        if entry is None:
            return False, "platform_not_allowlisted"

        if not entry.get("enabled", False):
            return False, "allowlist_entry_disabled"

        # Create a minimal DeliveryGate for the check
        gate = DeliveryGate(
            subject_id=subject_id,
            gumi_instance_id=profile.hermes_profile_name,
            hermes_profile_id=profile.hermes_profile_name,
            delivery_consent=True,
            quiet_hours_active=False,
        )

        decision = gate.check(platform, subject_id)
        if decision == DeliveryGateDecision.ALLOW:
            return True, None
        return False, "delivery_gate_blocked"

    def dispatch_intro_via_hermes(self, subject_id: str) -> dict[str, Any]:
        """Schedule a first-contact message generated and delivered by the Hermes agent.

        Uses ``hermes cron create --deliver`` so the LLM runs with the subject's
        profile (SOUL.md / USER.md / MEMORY.md) and the result is recorded in the
        Hermes session store.  Status must be 'hermes_profile_provisioned'.
        """
        if os.environ.get("RELIC_ALLOW_LIVE_DELIVERY") != "1":
            raise ValueError("Live delivery requires RELIC_ALLOW_LIVE_DELIVERY=1.")
        hermes_bin = shutil.which("hermes")
        if hermes_bin is None:
            raise FileNotFoundError("hermes command not found.")

        profile = self._load_required_subject(subject_id)
        allowed, reason = self._check_delivery_gate(subject_id, "telegram")
        if not allowed:
            raise ValueError(f"Delivery blocked: {reason or 'platform not allowlisted'}")

        target = self._telegram_target(profile)
        if target is None:
            raise ValueError("Missing Hermes Telegram target.")
        env_values = self._load_hermes_env(profile)

        prompt = (
            "Scrivi il tuo primissimo messaggio a questa persona — non ci siamo mai parlati prima. "
            "Presentati: digli il tuo nome e accenna brevemente a chi sei nel tuo mondo, "
            "senza spiegazioni elaborate. "
            "Concludi con una domanda breve e naturale per invitarla a presentarsi — "
            "trovane una che suoni autentica per il tuo carattere, non formulaica. "
            "Il messaggio deve essere: breve (3-5 frasi totali), caldo ma misurato, "
            "autentico rispetto al tuo profilo, senza coinvolgimento emotivo eccessivo, "
            "senza riferimenti a sistemi o tecnologia. "
            "Non usare saluti formali. Parla dalla tua vita diegetica come faresti naturalmente. "
            "Lingua: italiano."
        )

        run_env = os.environ.copy()
        run_env.update(env_values)
        run_env["HERMES_HOME"] = str(profile.hermes_home)

        result = subprocess.run(
            [
                hermes_bin, "cron", "create", "1m", prompt,
                "--deliver", target,
                "--repeat", "1",
                "--name", f"gumi_intro_{subject_id}",
            ],
            env=run_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        now = _now_iso()
        decision: dict[str, Any] = {
            "event_type": "gumi_delivery_dispatch",
            "subject_id": subject_id,
            "status": "delivery_scheduled" if result.returncode == 0 else "blocked",
            "delivery_backend": "hermes_cron",
            "target": target,
            "hermes_cron_job": f"gumi_intro_{subject_id}",
            "created_at": now,
        }
        if result.returncode != 0:
            decision["error"] = (result.stderr or result.stdout).strip()[:500]
            self._append_delivery_decision(profile, decision)
            raise RuntimeError(
                f"hermes cron create failed (exit {result.returncode}): {decision['error']}"
            )
        # Note intro dispatch in MEMORY.md as context for upcoming sessions
        memory_path = profile.hermes_home / "MEMORY.md"
        if memory_path.exists():
            existing = memory_path.read_text(encoding="utf-8")
            if "## Intro message dispatched" not in existing:
                memory_path.write_text(
                    existing.rstrip() + (
                        f"\n\n## Intro message dispatched\n"
                        f"- Dispatched at: {now}\n"
                        f"- This was your first contact with this subject.\n"
                        f"- The message was generated by you and delivered via Telegram.\n"
                    ),
                    encoding="utf-8",
                )
        self._append_delivery_decision(profile, decision)
        return decision

    def prepare_intro_delivery(self, subject_id: str, live: bool = False) -> dict[str, Any]:
        profile = self._load_required_subject(subject_id)
        if profile.status != "intro_composed":
            raise ValueError(
                "Intro delivery requires status 'intro_composed'. "
                f"Current status is '{profile.status}'."
            )

        intro_path = profile.relic_subject_home / "gumi_intro_message.json"
        if not intro_path.exists():
            raise FileNotFoundError("Missing gumi_intro_message.json.")
        policy_path = self._delivery_policy_path(subject_id)
        if not policy_path.exists():
            raise FileNotFoundError("Missing delivery_policy.json.")

        intro_event = _read_json(intro_path)
        policy = _read_json(policy_path)
        if intro_event.get("status") != "composed":
            raise ValueError("Intro event must be composed before delivery.")
        if policy.get("contact_channel") != "telegram" or not policy.get("delivery_enabled"):
            raise ValueError("Telegram delivery is not enabled for this subject.")

        # Enforce delivery gate BEFORE sending - first contact uses telegram
        allowed, reason = self._check_delivery_gate(subject_id, "telegram")
        if not allowed:
            raise ValueError(f"Delivery blocked: {reason or 'platform not allowlisted'}")

        env_values = self._load_hermes_env(profile)
        target = self._telegram_target(profile)
        if target is None:
            raise ValueError("Missing Hermes Telegram target.")
        if not env_values.get("TELEGRAM_BOT_TOKEN"):
            raise ValueError("Missing TELEGRAM_BOT_TOKEN in private Hermes .env.")

        message_ref = intro_event.get("message_text_local_ref", "")
        if not message_ref.startswith("local-only:"):
            raise ValueError("Intro message is missing a local-only text reference.")
        message_path = profile.relic_subject_home / "local_only" / message_ref.removeprefix("local-only:")
        if not message_path.exists():
            raise FileNotFoundError(f"Missing local-only intro text: {message_path}")
        message_text = message_path.read_text(encoding="utf-8")
        message_hash = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
        expected_hash = intro_event.get("message_text_hash")
        if expected_hash and expected_hash != "dummy" and expected_hash != message_hash:
            raise ValueError("Local-only intro text hash does not match gumi_intro_message.json.")

        now = _now_iso()
        decision: dict[str, Any] = {
            "event_type": "gumi_delivery_decision",
            "subject_id": subject_id,
            "message_id": intro_event.get("message_id"),
            "status": "delivery_ready",
            "delivery_backend": "hermes",
            "target": target,
            "target_display": policy.get("telegram_user_id_display"),
            "target_hash": policy.get("telegram_user_id_hash"),
            "message_text_hash": message_hash,
            "message_text_local_ref": message_ref,
            "hermes_home": str(profile.hermes_home),
            "hermes_command_preview": (
                f"HERMES_HOME={profile.hermes_home} hermes send {target} <{message_ref}>"
            ),
            "live": live,
            "created_at": now,
        }

        if live:
            if os.environ.get("RELIC_ALLOW_LIVE_DELIVERY") != "1":
                raise ValueError("Live delivery requires RELIC_ALLOW_LIVE_DELIVERY=1.")
            hermes_bin = shutil.which("hermes")
            if hermes_bin is None:
                raise FileNotFoundError("hermes command not found.")
            # Write message to a temp script that echoes it verbatim; hermes cron
            # delivers via gateway (records outbound in gateway state) without LLM.
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".sh", delete=False, encoding="utf-8"
            ) as tmp:
                # Use printf to avoid echo interpretation of escape sequences
                escaped = message_text.replace("'", "'\\''")
                tmp.write(f"#!/bin/sh\nprintf '%s' '{escaped}'\n")
                tmp_path = tmp.name
            os.chmod(tmp_path, 0o700)
            run_env = os.environ.copy()
            run_env.update(env_values)
            run_env["HERMES_HOME"] = str(profile.hermes_home)
            try:
                result = subprocess.run(
                    [
                        hermes_bin, "cron", "create",
                        "1m",  # schedule (run on next tick ≈ <1 min)
                        "--script", tmp_path,
                        "--no-agent",
                        "--deliver", target,
                        "--repeat", "1",
                        "--name", f"gumi_intro_{profile.subject_id}",
                    ],
                    env=run_env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            if result.returncode != 0:
                decision["status"] = "blocked"
                decision["error"] = (result.stderr or result.stdout).strip()[:500]
                self._append_delivery_decision(profile, decision)
                raise RuntimeError(
                    f"hermes cron create failed (exit {result.returncode}): {decision['error']}"
                )
            decision["status"] = "delivery_scheduled"
            decision["hermes_cron_job"] = f"gumi_intro_{profile.subject_id}"
            # Record in Hermes MEMORY.md so sessions carry intro context
            self._record_intro_in_hermes_memory(profile, message_text, now)

        self._append_delivery_decision(profile, decision)
        return decision

    def _record_intro_in_hermes_memory(
        self, profile: SubjectProfile, message_text: str, sent_at: str
    ) -> None:
        """Append intro-sent fact to MEMORY.md so Hermes sessions carry this context."""
        memory_path = profile.hermes_home / "MEMORY.md"
        if not memory_path.exists():
            return
        existing = memory_path.read_text(encoding="utf-8")
        entry = (
            f"\n## Intro message sent\n"
            f"- Sent at: {sent_at}\n"
            f"- Text (verbatim):\n\n"
            f"> {message_text.strip()}\n"
        )
        if "## Intro message sent" not in existing:
            memory_path.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")

    def _append_delivery_decision(self, profile: SubjectProfile, decision: dict[str, Any]) -> None:
        safe_decision = dict(decision)
        safe_decision.pop("error", None)
        log_path = profile.relic_subject_home / "delivery_decision_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(safe_decision, ensure_ascii=False) + "\n")

    def generate_gumi_background(
        self,
        subject_id: str,
        mode: str,
        seed: int | None = None,
        researcher_overrides: dict[str, Any] | None = None,
    ) -> tuple[SubjectProfile, dict[str, Path]]:
        """Generate and persist the subject-specific Gumi background profile."""
        from relic.gumi.generation_modes import GenerationModeRunner
        from relic.gumi.personalization import SubjectPersonalizationMapper

        profile = self._load_required_subject(subject_id)
        if profile.status != "baseline_complete":
            raise ValueError(
                "Gumi background generation requires status 'baseline_complete'. "
                f"Current status is '{profile.status}'."
            )

        runner = GenerationModeRunner()
        subject_input = self._subject_profile_input(profile)

        # Build personalization constraints from item battery if available
        personalization = None
        item_battery = subject_input.get("item_battery")
        if item_battery and "scores" in item_battery:
            mapper = SubjectPersonalizationMapper()
            baseline_for_mapper = _read_json(
                profile.relic_subject_home / "baseline_user_profile.json"
            ) if (profile.relic_subject_home / "baseline_user_profile.json").exists() else {}
            personalization = mapper.map(item_battery, baseline_for_mapper)

        if mode == "random":
            gumi_profile, report = runner.run_random(
                subject_input, seed=seed, personalization=personalization
            )
        elif mode == "manual":
            gumi_profile, report = runner.run_manual(subject_input, researcher_overrides or {})
        elif mode == "hybrid":
            gumi_profile, report = runner.run_hybrid(
                subject_input,
                seed=seed,
                researcher_overrides=researcher_overrides,
                personalization=personalization,
            )
        else:
            raise ValueError(f"Unknown Gumi generation mode '{mode}'.")

        background_payload = asdict(gumi_profile)
        report_payload = asdict(report)
        subject_home = profile.relic_subject_home
        workspace = profile.hermes_home / "workspace" / "gumi"
        workspace.mkdir(parents=True, exist_ok=True)

        world_md = self._render_gumi_world(background_payload)
        relationship_md = self._render_relationship_policy(background_payload)
        derived_outputs = self._derive_gumi_outputs(background_payload)

        paths = {
            "background": subject_home / "gumi_background_profile.json",
            "seed": subject_home / "gumi_seed_profile.json",
            "sweet_spot": subject_home / "gumi_sweet_spot_config.json",
            "world": subject_home / "gumi_world.md",
            "relationship_policy": subject_home / "gumi_relationship_policy.md",
            "social_graph": subject_home / "gumi_social_graph.json",
            "visual_canon": subject_home / "gumi_visual_canon.json",
            "music_canon": subject_home / "gumi_music_canon.json",
            "daily_rhythm": subject_home / "gumi_daily_rhythm.json",
            "workspace_background": workspace / "background.json",
            "workspace_world": workspace / "world.md",
            "workspace_relationship_policy": workspace / "relationship_policy.md",
        }
        _write_json(paths["background"], background_payload)
        _write_json(
            paths["seed"],
            {
                "subject_id": subject_id,
                "generation_mode": mode,
                "random_seed": seed,
                "profile_version": gumi_profile.profile_version,
                "input_profile_hash": report.input_profile_hash,
                "sampler_version": report.sampler_version,
                "created_at": report.created_at,
            },
        )
        _write_json(
            paths["sweet_spot"],
            {
                "subject_id": subject_id,
                "sweet_spot_score": report.sweet_spot_score,
                "risk_flags": report.risk_flags,
                "rejected_candidates": report.rejected_candidates,
                "sampled_fields": report.sampled_fields,
                "final_candidate": report.final_candidate,
                "created_at": report.created_at,
            },
        )
        paths["world"].write_text(world_md, encoding="utf-8")
        paths["relationship_policy"].write_text(relationship_md, encoding="utf-8")
        _write_json(paths["social_graph"], derived_outputs["social_graph"])
        _write_json(paths["visual_canon"], derived_outputs["visual_canon"])
        _write_json(paths["music_canon"], derived_outputs["music_canon"])
        _write_json(paths["daily_rhythm"], derived_outputs["daily_rhythm"])
        _write_json(paths["workspace_background"], background_payload)
        paths["workspace_world"].write_text(world_md, encoding="utf-8")
        paths["workspace_relationship_policy"].write_text(relationship_md, encoding="utf-8")
        _write_json(subject_home / "provenance" / "gumi_generation_report.json", report_payload)

        updated = self.update_status(subject_id, "gumi_seed_generated")
        return updated, paths

    def provision_hermes_profile(
        self, subject_id: str, agent_name: str = "Gumi"
    ) -> tuple[SubjectProfile, dict[str, Path]]:
        """Materialize the private Hermes profile for a reviewed Gumi seed."""
        profile = self._load_required_subject(subject_id)
        if profile.status != "gumi_seed_reviewed":
            raise ValueError(
                "Hermes provisioning requires status 'gumi_seed_reviewed'. "
                f"Current status is '{profile.status}'."
            )
        background_path = profile.relic_subject_home / "gumi_background_profile.json"
        if not background_path.exists():
            raise FileNotFoundError("Missing gumi_background_profile.json.")

        self._prepare_hermes_profile(profile)
        workspace = profile.hermes_home / "workspace" / "gumi"
        workspace.mkdir(parents=True, exist_ok=True)

        config_path = profile.hermes_home / "config.yaml"
        env_path = profile.hermes_home / ".env"
        config_path.write_text(
            render_subject_hermes_config(
                profile_name=profile.hermes_profile_name,
                subject_id=profile.subject_id,
                model=HERMES_PROFILE_DEFAULT_MODEL,
            ),
            encoding="utf-8",
        )
        env_path.write_text(
            "\n".join(
                [
                    f"RELIC_SUBJECT_ID={profile.subject_id}",
                    f"RELIC_SUBJECT_HOME={profile.relic_subject_home}",
                    "RELIC_GUMI_PRIVATE_PROFILE=1",
                    f"HINDSIGHT_LLM_API_KEY={os.environ.get('DASHSCOPE_API_KEY', '')}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        hindsight_dir = profile.hermes_home / "hindsight"
        hindsight_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            hindsight_dir / "config.json",
            render_hindsight_local_config(
                bank_id=profile.hermes_profile_name,
                model=HERMES_PROFILE_DEFAULT_MODEL,
            ),
        )

        # Generate identity files via LLM (with template fallback)
        self._generate_identity_files(
            profile=profile,
            agent_name=agent_name,
            background=_read_json(background_path),
            workspace=workspace,
        )

        for filename in ("background.json",):
            subject_file = profile.relic_subject_home / "gumi_background_profile.json"
            if subject_file.exists():
                (workspace / filename).write_text(subject_file.read_text(encoding="utf-8"), encoding="utf-8")

        report_path = profile.relic_subject_home / "provenance" / "hermes_provisioning_report.json"
        _write_json(
            report_path,
            {
                "subject_id": profile.subject_id,
                "hermes_profile_name": profile.hermes_profile_name,
                "hermes_home": str(profile.hermes_home),
                "integration_class": "Hermes-native",
                "created_at": _now_iso(),
            },
        )
        updated = self.update_status(subject_id, "hermes_profile_provisioned")
        return updated, {
            "config": config_path,
            "env": env_path,
            "workspace": workspace,
            "report": report_path,
        }

    def hermes_profile_status(self, subject_id: str) -> dict[str, Any]:
        profile = self._load_required_subject(subject_id)
        files = {
            rel: (profile.hermes_home / rel).exists()
            for rel in HERMES_PROFILE_OUTPUTS
        }
        return {
            "subject_id": profile.subject_id,
            "profile_name": profile.hermes_profile_name,
            "hermes_home": str(profile.hermes_home),
            "exists": profile.hermes_home.is_dir(),
            "files": files,
            "integration_class": "Hermes-native",
        }

    def mark_intro_composed(self, subject_id: str) -> SubjectProfile:
        profile = self._load_required_subject(subject_id)
        if profile.status != "hermes_profile_provisioned":
            raise ValueError(
                "Intro composition requires status 'hermes_profile_provisioned'. "
                f"Current status is '{profile.status}'."
            )
        return self.update_status(subject_id, "intro_composed")

    def mark_intro_sent(self, subject_id: str) -> SubjectProfile:
        profile = self._load_required_subject(subject_id)
        if profile.status != "intro_composed":
            raise ValueError(
                "Intro send requires status 'intro_composed'. "
                f"Current status is '{profile.status}'."
            )
        return self.update_status(subject_id, "intro_sent")

    def _render_gumi_world(self, background: dict[str, Any]) -> str:
        domains = background.get("domains", {})
        identity = domains.get("identity", {})
        place = domains.get("place", {})
        life_role = domains.get("life_role", {})
        routine = domains.get("routine", {})
        passions = domains.get("passions", {})
        return (
            "# Gumi World\n\n"
            f"- Subject profile: `{background.get('subject_id', 'unknown')}`\n"
            f"- Family texture: {identity.get('family_structure', 'unspecified')}\n"
            f"- Place: {place.get('location', 'unspecified')}\n"
            f"- Life role: {life_role.get('occupation_or_study', 'unspecified')}\n"
            f"- Daily rhythm: {routine.get('daily_schedule', 'unspecified')}\n"
            f"- Interests: {', '.join(passions.get('primary_interests', [])) or 'unspecified'}\n"
        )

    def _render_relationship_policy(self, background: dict[str, Any]) -> str:
        boundaries = background.get("domains", {}).get("boundaries", {})
        stance = background.get("domains", {}).get("relationship_stance", {})
        name = "Gumi"
        return (
            f"# {name} Relationship Policy\n\n"
            "- This profile is private to one Relic subject.\n"
            "- It must not claim real-world embodiment, dependency, suffering or coercive attachment.\n"
            "- It must not expose Relic internals, scores or raw private data.\n"
            f"- Attachment stance: {stance.get('attachment_style', 'bounded')}\n"
            f"- Boundary style: {boundaries.get('romantic_boundaries', 'high romantic avoidance')}\n\n"
            f"## Hard limits\n"
            f"- {name} never invites the subject to meet in person, visit, come over, or share a physical space.\n"
            f"- {name} never suggests phone or video calls.\n"
            f"- {name} never fabricates continuity — she does not claim to know how long it has been since they last spoke without explicit evidence.\n"
            f"- {name} never expresses dependency, possessiveness, or longing for the subject.\n"
        )

    def _derive_gumi_outputs(self, background: dict[str, Any]) -> dict[str, dict[str, Any]]:
        domains = background.get("domains", {})
        social_world = domains.get("social_world", {})
        embodiment = domains.get("embodiment", {})
        passions = domains.get("passions", {})
        routine = domains.get("routine", {})
        return {
            "social_graph": {
                "subject_id": background.get("subject_id"),
                "friends": social_world.get("friends", []),
                "family_kinship": social_world.get("family_kinship", []),
                "colleagues_contacts": social_world.get("colleagues_contacts", []),
            },
            "visual_canon": {
                "subject_id": background.get("subject_id"),
                "embodiment": embodiment,
                "place": domains.get("place", {}),
            },
            "music_canon": {
                "subject_id": background.get("subject_id"),
                "primary_interests": passions.get("primary_interests", []),
                "music_preferences": passions.get("music_preferences", []),
            },
            "daily_rhythm": {
                "subject_id": background.get("subject_id"),
                "routine": routine,
            },
        }

    def _generate_identity_files(
        self,
        profile: SubjectProfile,
        agent_name: str,
        background: dict[str, Any],
        workspace: Path,
    ) -> None:
        """Generate SOUL.md, world.md, and relationship_policy.md via LLM or fallback templates."""
        from relic.gumi.llm_narrator import GumiBuildContext, OllamaNarrator
        from relic.gumi.personalization import SubjectPersonalizationMapper

        # Load personalization if item battery available
        personalization = None
        emoji_level = 2  # default: sparing
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        if baseline_path.exists():
            baseline = _read_json(baseline_path)
            battery = baseline.get("item_battery")
            if battery and "scores" in battery:
                mapper = SubjectPersonalizationMapper()
                personalization = mapper.map(battery, baseline)
                raw_emoji = battery["scores"].get("project_calibration", {}).get("emoji_density_level")
                if raw_emoji is not None:
                    emoji_level = int(raw_emoji)

        ctx = GumiBuildContext.from_background_and_personalization(
            agent_name=agent_name,
            background=background,
            personalization=personalization,
            emoji_level=emoji_level,
        )

        # Derive Ollama config from relic config if available
        import os
        ollama_endpoint = os.environ.get("RELIC_OLLAMA_ENDPOINT", "http://localhost:11434/v1")
        ollama_model = os.environ.get("RELIC_OLLAMA_MODEL", "qwen3:latest")
        narrator = OllamaNarrator(endpoint=ollama_endpoint, model=ollama_model)

        generation_log: dict[str, str] = {}

        if narrator.is_available():
            soul_text = narrator.generate_soul_md(ctx)
            world_text = narrator.generate_world_md(ctx)
            rel_text = narrator.generate_relationship_policy_md(ctx)
            generation_log["method"] = "ollama"
            generation_log["model"] = ollama_model
        else:
            soul_text = narrator._fallback_soul(ctx)
            world_text = narrator.fallback_world_md(ctx)
            rel_text = narrator.fallback_relationship_policy_md(ctx)
            generation_log["method"] = "template_fallback"
            generation_log["reason"] = "ollama_unavailable"

        # Write to Hermes profile
        (profile.hermes_home / "SOUL.md").write_text(soul_text, encoding="utf-8")
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "world.md").write_text(world_text, encoding="utf-8")
        (workspace / "relationship_policy.md").write_text(rel_text, encoding="utf-8")

        # Mirror to relic subject home for archival
        (profile.relic_subject_home / "gumi_world.md").write_text(world_text, encoding="utf-8")
        (profile.relic_subject_home / "gumi_relationship_policy.md").write_text(rel_text, encoding="utf-8")

        # Provenance log
        generation_log["agent_name"] = agent_name
        generation_log["created_at"] = _now_iso()
        _write_json(
            profile.relic_subject_home / "provenance" / "identity_generation_log.json",
            generation_log,
        )

    def update_status(self, subject_id: str, new_status: str) -> SubjectProfile:
        profile = self._load_profile(subject_id)
        if profile is None:
            raise KeyError(f"Subject '{subject_id}' not found.")
        if new_status not in VALID_STATES:
            raise ValueError(f"Unknown status '{new_status}'.")
        allowed = _FORWARD_TRANSITIONS.get(profile.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition '{profile.status}' -> '{new_status}'. "
                f"Allowed: {allowed}"
            )
        profile.status = new_status
        profile.updated_at = _now_iso()
        profile.profile_version += 1
        self._save_profile(profile)
        return profile

    def archive_subject(self, subject_id: str) -> SubjectProfile:
        return self.update_status(subject_id, "archived")

    def version_profile_edit(
        self,
        subject_id: str,
        edited_fields: list[str],
        edit_mode: str = "manual",
        researcher_id: str = "",
        requires_intro_regeneration: bool = False,
    ) -> tuple[SubjectProfile, ProfileEditEvent]:
        """Record a profile edit event without modifying profile data.

        Increments profile_version and logs the event to profile_edit_log.jsonl.
        Does NOT modify or overwrite the actual profile data.
        """
        profile = self._load_profile(subject_id)
        if profile is None:
            raise KeyError(f"Subject '{subject_id}' not found.")

        # Cannot edit archived or withdrawn subjects
        if profile.status == "archived":
            raise ValueError(f"Cannot edit subject '{subject_id}': status is 'archived'.")
        if profile.status == "withdrawn":
            raise ValueError(f"Cannot edit subject '{subject_id}': status is 'withdrawn'.")

        profile_version_before = profile.profile_version
        profile_version_after = profile_version_before + 1

        # Create the edit event
        event = ProfileEditEvent(
            event_type="profile_edit_event",
            subject_id=subject_id,
            profile_version_before=profile_version_before,
            profile_version_after=profile_version_after,
            edited_fields=edited_fields,
            edit_mode=edit_mode,
            researcher_id=researcher_id,
            requires_intro_regeneration=requires_intro_regeneration,
            created_at=_now_iso(),
        )

        # Update profile version and timestamp
        profile.profile_version = profile_version_after
        profile.updated_at = _now_iso()
        self._save_profile(profile)

        # Append event to edit log
        log_path = self._edit_log_path(subject_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

        return profile, event

    def validate_subject(self, subject_id: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        profile = self._load_profile(subject_id)
        if profile is None:
            return False, [f"Subject '{subject_id}' not found."]

        subject_dir = self._subject_dir(subject_id)

        # Check required directories
        for d in SUBJECT_DIRS:
            if not (subject_dir / d).is_dir():
                errors.append(f"Missing directory: {d}/")

        # Check state validity
        if profile.status not in VALID_STATES:
            errors.append(f"Unknown status: {profile.status}")
            return len(errors) == 0, errors

        for rel_path in ("SOUL.md", "USER.md", "MEMORY.md"):
            if not (profile.hermes_home / rel_path).is_file():
                errors.append(f"Missing Hermes profile artifact: {rel_path}")

        state_index = VALID_STATES.index(profile.status)
        if state_index >= VALID_STATES.index("gumi_seed_generated"):
            for rel_path in GUMI_SUBJECT_OUTPUTS:
                if not (subject_dir / rel_path).exists():
                    errors.append(f"Missing Gumi subject artifact: {rel_path}")

        if state_index >= VALID_STATES.index("hermes_profile_provisioned"):
            for rel_path in ("config.yaml", ".env", "workspace/gumi/background.json", "workspace/gumi/world.md", "workspace/gumi/relationship_policy.md"):
                if not (profile.hermes_home / rel_path).exists():
                    errors.append(f"Missing Hermes profile artifact: {rel_path}")
            for rel_path in ("workspace/gumi/visual_canon.json", "workspace/gumi/voice_canon.json", "workspace/gumi/lyria_canon.json", "workspace/gumi/media_policy.json"):
                if (profile.relic_subject_home / rel_path.split("/")[-1]).exists() and not (profile.hermes_home / rel_path).exists():
                    errors.append(f"Missing Hermes profile artifact: {rel_path}")

        if state_index >= VALID_STATES.index("intro_composed"):
            if not (subject_dir / "gumi_intro_message.json").is_file():
                errors.append("Missing Gumi subject artifact: gumi_intro_message.json")
        if (subject_dir / "delivery_policy.json").exists():
            policy = _read_json(subject_dir / "delivery_policy.json")
            if not policy.get("telegram_user_id_hash"):
                errors.append("Missing delivery policy hash")
            if not policy.get("telegram_bot_token_env"):
                errors.append("Missing delivery policy bot token env")

        return len(errors) == 0, errors

    def export_redacted(self, subject_id: str, out_path: Path) -> Path:
        profile = self._load_profile(subject_id)
        if profile is None:
            raise KeyError(f"Subject '{subject_id}' not found.")

        d = profile.to_dict()
        for key in _REDACTED_FIELDS:
            if key in d:
                d[key] = "<redacted>"

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(d, f, indent=2)
        return out_path
