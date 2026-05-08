"""Bootstrap TUI for subject profile creation and editing.

This module provides a text-mode user interface (no curses) that guides
researchers through creating new subject profiles or editing existing ones.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TextIO

from relic.bootstrap import build_pr28_bootstrap_outputs, subject_data_from_bootstrap_state
from relic.profile.registry import ProfileRegistry, SubjectProfile, VALID_STATES
from relic.gumi.initial_contact import InitialContactComposer, CalibrationConfig
from relic.profile.baseline_artifact import build_baseline_artifact, write_baseline_artifact
from relic.profile._bootstrap_steps.item_battery import (
    battery_to_baseline_sections,
    collect_item_battery,
)
from relic.profile._bootstrap_steps.boundaries import collect_boundaries
from relic.profile._bootstrap_steps.consent import collect_consent_record
from relic.profile._bootstrap_steps.delivery_config import collect_delivery_config
from relic.profile._bootstrap_steps.gumi_review import review_gumi_background
from relic.profile._bootstrap_steps.gumi_overrides import collect_gumi_overrides
from relic.profile._bootstrap_steps.first_contact_controls import run_first_contact_controls
from relic.gumi_plugin.cron_wiring import provision_for_subject


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _calibration_from_baseline(
    relational_expectations: dict,
    interaction_preferences: dict,
    researcher_coded_fields: dict,
) -> CalibrationConfig:
    """Derive CalibrationConfig from collected baseline data with safe defaults."""

    def _val(d: dict, key: str) -> str:
        entry = d.get(key, {})
        if isinstance(entry, dict):
            return (entry.get("value") or "").lower()
        return ""

    tone = _val(relational_expectations, "desired_relationship_tone")
    disclosure = _val(relational_expectations, "disclosure_comfort_level")
    comm_style = _val(researcher_coded_fields, "communication_style")
    msg_length = _val(interaction_preferences, "message_length_preference")

    warmth = "high" if any(k in tone for k in ("cald", "warm", "amich")) else "medium"
    self_disclosure = "high" if any(k in disclosure for k in ("alto", "high", "molt")) else "low"
    directness = "high" if any(k in comm_style for k in ("dirett", "direct")) else "medium"
    diegetic_density = "high" if any(k in msg_length for k in ("lung", "long", "dett")) else "medium"

    return CalibrationConfig(
        warmth=warmth,
        playfulness="medium",
        directness=directness,
        initiative="medium",
        self_disclosure=self_disclosure,
        boundary_strength="medium",
        romantic_avoidance="high",
        diegetic_density=diegetic_density,
    )


class BootstrapTUI:
    """Text-mode TUI for bootstrapping and editing subject profiles.

    Args:
        registry: ProfileRegistry instance for subject management.
        io_in: Input stream for testing (default: stdin).
        io_out: Output stream for testing (default: stdout).
    """

    def __init__(
        self,
        registry: ProfileRegistry,
        io_in: Optional[TextIO] = None,
        io_out: Optional[TextIO] = None,
    ) -> None:
        self.registry = registry
        self.io_in = io_in or sys.stdin
        self.io_out = io_out or sys.stdout
        self._session_log_path: Optional[Path] = None
        self._edit_log_path: Optional[Path] = None

    def _log_step(self, step: str, value: str) -> None:
        if self._session_log_path is not None:
            entry = {"step": step, "value": value, "ts": _now_iso()}
            with open(self._session_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def _log_edit_step(self, step: str, value: str) -> None:
        if self._edit_log_path is not None:
            entry = {"step": step, "value": value, "ts": _now_iso()}
            with open(self._edit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def _print(self, message: str) -> None:
        print(message, file=self.io_out)

    def _prompt(self, question: str, default: Optional[str] = None) -> str:
        """Print a question and read user input, applying default if empty."""
        prompt_text = question
        if default is not None:
            prompt_text = f"{question} [{default}]"
        print(prompt_text, file=self.io_out)

        if hasattr(self.io_in, "read"):
            raw = self.io_in.readline()
            if raw is None:
                raw = ""
        else:
            raw = input()

        raw = raw.strip()
        return raw if raw else (default if default is not None else "")

    def _confirm(self, question: str) -> bool:
        """Print a yes/no question and return the boolean answer."""
        while True:
            answer = self._prompt(f"{question} (yes/no)", default=None)
            lower = answer.lower()
            if lower in ("y", "yes"):
                return True
            elif lower in ("n", "no", ""):
                return False
            else:
                print("Please answer 'yes' or 'no'.", file=self.io_out)

    def run_init(
        self,
        subject_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
    ) -> SubjectProfile:
        """Run the initialization wizard for a new subject."""
        self._print("\n=== Subject Profile Bootstrap ===\n")

        # Step 1: subject_id
        if subject_id is None:
            subject_id = self._prompt("Enter subject ID")
            if not subject_id:
                subject_id = f"subj_{uuid.uuid4().hex[:8]}"
                self._print(f"Auto-generated subject ID: {subject_id}")
        else:
            self._print(f"Subject ID: {subject_id}")

        # Step 2: experiment_id
        if experiment_id is None:
            experiment_id = self._prompt("Enter experiment ID")
            while not experiment_id:
                self._print("Experiment ID is required.")
                experiment_id = self._prompt("Enter experiment ID")
        else:
            self._print(f"Experiment ID: {experiment_id}")

        # Step 3: structured item battery (TIPI + ECR-RS + project items + safety gates).
        item_battery = collect_item_battery(self.io_in, self.io_out)
        baseline_method = item_battery["baseline_method"]
        baseline_sections = battery_to_baseline_sections(item_battery)
        self_report_fields = baseline_sections["self_report_fields"]
        researcher_coded_fields = baseline_sections["researcher_coded_fields"]
        interaction_preferences = baseline_sections["interaction_preferences"]
        relational_expectations = baseline_sections["relational_expectations"]

        # Step 3b: Boundaries, opt-out categories, risk flags
        boundaries_data = collect_boundaries(self.io_in, self.io_out)

        # Step 3g: Consent record
        consent_record = collect_consent_record(self.io_in, self.io_out)

        # Step 4: Gumi generation mode — always hybrid; structured battery already provides
        # all calibration inputs. Optional domain overrides remain available.
        gumi_mode = "hybrid"
        gumi_overrides, gumi_name = collect_gumi_overrides(self.io_in, self.io_out, mode=gumi_mode)

        # Step 5: Hermes provisioning
        self._print("\n--- Hermes Provisioning ---")
        hermes_provision = self._confirm("Do you want to provision a Hermes profile?")
        hermes_value = "yes" if hermes_provision else "no"

        # Step 5b: Delivery configuration (gated by consent.delivery)
        delivery_config = collect_delivery_config(self.io_in, self.io_out, consent_record)

        # Create the profile via registry
        self._print(f"\nCreating subject '{subject_id}'...")
        profile = self.registry.create_subject(subject_id, experiment_id)

        # Ensure profile_edit_log.jsonl exists (required by SUBJECT_FILES contract)
        edit_log = profile.relic_subject_home / "profile_edit_log.jsonl"
        if not edit_log.exists():
            edit_log.touch()

        # Set up session log path
        self._session_log_path = profile.relic_subject_home / "bootstrap_session.jsonl"
        self._session_log_path.parent.mkdir(parents=True, exist_ok=True)
        if self._session_log_path.exists():
            self._session_log_path.unlink()

        # Log collected steps
        self._log_step("subject_id_entered", subject_id)
        self._log_step("experiment_id_entered", experiment_id)
        self._log_step("baseline_method_selected", baseline_method)
        self._log_step("item_battery_collected", str(len(item_battery["responses"])))
        self._log_step("self_report_fields_collected", str(len(self_report_fields)))
        self._log_step("researcher_coded_fields_collected", str(len(researcher_coded_fields)))
        self._log_step("interaction_preferences_collected", str(len(interaction_preferences)))
        self._log_step("relational_expectations_collected", str(len(relational_expectations)))
        self._log_step("boundaries_collected", str(len(boundaries_data)))
        self._log_step("consent_collected", "yes")
        self._log_step("gumi_mode_selected", gumi_mode)
        self._log_step("gumi_name", gumi_name)
        self._log_step("gumi_overrides_collected", str(len(gumi_overrides)))
        self._log_step("hermes_provisioning", hermes_value)
        self._log_step("delivery_config_collected", "yes" if delivery_config.get("delivery_enabled") else "no")

        # Status transitions + Gumi generation + review loop
        try:
            profile = self.registry.update_status(subject_id, "baseline_in_progress")
            self._log_step("baseline_status", profile.status)
            profile = self.registry.update_status(subject_id, "baseline_complete")
            self._log_step("baseline_status", profile.status)

            # Gumi generation with researcher review loop
            regen_idx = 0
            while True:
                if regen_idx == 0:
                    profile, _ = self.registry.generate_gumi_background(
                        subject_id,
                        mode=gumi_mode,
                        researcher_overrides=gumi_overrides if gumi_mode != "random" else None,
                    )
                    self._log_step("gumi_seed_generated", gumi_mode)
                else:
                    # Subsequent regenerations bypass status transitions
                    from relic.gumi.generation_modes import GenerationModeRunner
                    import random as _rng_mod
                    _seed = _rng_mod.randint(0, 2 ** 31)
                    runner = GenerationModeRunner()
                    subject_input = {"subject_id": subject_id}
                    if gumi_mode == "random":
                        gp, _ = runner.run_random(subject_input, seed=_seed)
                    elif gumi_mode == "manual":
                        gp, _ = runner.run_manual(subject_input, gumi_overrides or {})
                    else:
                        gp, _ = runner.run_hybrid(
                            subject_input, seed=_seed, researcher_overrides=gumi_overrides
                        )
                    bp = profile.relic_subject_home / "gumi_background_profile.json"
                    bp.write_text(
                        json.dumps(asdict(gp), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )

                regen_idx += 1
                background_path = profile.relic_subject_home / "gumi_background_profile.json"
                gumi_profile_dict = json.loads(background_path.read_text(encoding="utf-8"))
                gumi_action = review_gumi_background(self.io_in, self.io_out, gumi_profile_dict)
                self._log_step("gumi_review_action", gumi_action)
                if gumi_action == "accept":
                    break
                if gumi_action == "abort":
                    self._print("Bootstrap interrupted during Gumi review.")
                    return profile
                # "regenerate" → next iteration

        except Exception as exc:
            self._log_step("gumi_seed_generation_failed", str(exc))

        # Write baseline artifact using the canonical builder (baseline_artifact.py)
        researcher_id = consent_record.get("recorded_by_researcher_id", "")
        bootstrap_session_id = str(uuid.uuid4())
        state = {
            "bootstrap_session_id": bootstrap_session_id,
            "researcher_id": researcher_id,
            "subject_id": subject_id,
            "baseline_method": baseline_method,
            "self_report_fields": self_report_fields,
            "researcher_coded_fields": researcher_coded_fields,
            "interaction_preferences": interaction_preferences,
            "relational_expectations": relational_expectations,
            "boundaries": boundaries_data.get("boundaries", {}),
            "opt_out_categories": boundaries_data.get(
                "opt_out_categories", {"values": [], "origin": "subject-stated"}
            ),
            "risk_flags": boundaries_data.get("risk_flags", []),
            "item_battery": item_battery,
        }
        write_baseline_artifact(profile.relic_subject_home, build_baseline_artifact(state))
        self._log_step("baseline_artifact_written", "baseline_user_profile.json")
        (profile.relic_subject_home / "item_battery_response.json").write_text(
            json.dumps(item_battery, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._log_step("item_battery_response_written", "item_battery_response.json")

        # Write consent artifact
        (profile.relic_subject_home / "consent_record.json").write_text(
            json.dumps(consent_record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._log_step("consent_record_written", "consent_record.json")

        # Write PR28 normalized bootstrap outputs for sweet-spot review.
        pr28_subject_data = subject_data_from_bootstrap_state(
            subject_id=subject_id,
            experiment_id=experiment_id,
            state=state,
            consent_record=consent_record,
        )
        build_pr28_bootstrap_outputs(
            profile.relic_subject_home,
            pr28_subject_data,
            generation_mode=gumi_mode,
        )
        self._log_step("pr28_bootstrap_outputs_written", "sweet_spot_report.json")

        # Hermes provisioning
        if hermes_provision:
            try:
                current = self.registry.get_subject(subject_id)
                if current is not None and current.status == "gumi_seed_generated":
                    profile = self.registry.update_status(subject_id, "gumi_seed_reviewed")
                    self._log_step("gumi_seed_reviewed", profile.status)
                # B3: pass agent_name so SOUL.md is generated with the correct name
                profile, _ = self.registry.provision_hermes_profile(subject_id, agent_name=gumi_name)
                self._log_step("hermes_profile_provisioned", str(profile.hermes_home))

                # WIRE04: provision no-agent cron jobs (checkin, followup, proactivity)
                try:
                    gumi_instance_id = f"gumi-{subject_id}"
                    hermes_profile_id = profile.hermes_profile_name
                    cron_result = provision_for_subject(
                        subject_id=subject_id,
                        gumi_instance_id=gumi_instance_id,
                        hermes_profile_id=hermes_profile_id,
                        schedule="*/30 * * * *",
                        dry_run=True,
                    )
                    self._log_step("no_agent_cron_provisioned", str(list(cron_result.get("scripts", {}).keys())))
                except Exception as exc:
                    self._log_step("no_agent_cron_provisioning_failed", str(exc))

                # B1: wire Telegram delivery if consent given and config collected
                telegram_user_id = delivery_config.get("telegram_user_id", "")
                telegram_bot_token_env = delivery_config.get("telegram_bot_token_env", "")
                if (
                    consent_record.get("delivery")
                    and telegram_user_id
                    and telegram_bot_token_env
                ):
                    try:
                        quiet_start = delivery_config.get("quiet_start", "22:00")
                        quiet_end = delivery_config.get("quiet_end", "08:00")
                        freq_count = delivery_config.get("freq_count", "1")
                        freq_window = delivery_config.get("freq_window", "day")
                        self.registry.configure_telegram_delivery(
                            subject_id=subject_id,
                            telegram_bot_token_env=telegram_bot_token_env,
                            telegram_user_id=telegram_user_id,
                            quiet_hours=f"{quiet_start}-{quiet_end}",
                            maximum_contact_frequency=f"{freq_count}/{freq_window}",
                            consent_for_active_elicitation=consent_record.get("active_elicitation", False),
                            consent_for_generated_images=consent_record.get("generated_images", False),
                            consent_for_generated_audio=consent_record.get("generated_audio", False),
                            consent_for_generated_music=consent_record.get("generated_music", False),
                        )
                        self._log_step("delivery_configured", "telegram")
                    except Exception as exc:
                        self._log_step("delivery_config_failed", str(exc))

                # B2: provision cron specs — maintenance always, initiative if delivery configured
                try:
                    cron_families = ["maintenance"]
                    delivery_policy_path = profile.relic_subject_home / "delivery_policy.json"
                    if delivery_policy_path.exists():
                        cron_families.append("initiative")
                    self.registry.provision_subject_cron_specs(
                        subject_id, families=cron_families, dry_run=True
                    )
                    self._log_step("cron_provisioned", ",".join(cron_families))
                except Exception as exc:
                    self._log_step("cron_provisioning_failed", str(exc))

            except Exception as exc:
                self._log_step("hermes_provisioning_failed", str(exc))

        # Compose first contact and researcher controls
        self._print("\n--- First Message ---")
        send_first = self._confirm(
            f"Should {gumi_name} send the first message to initiate contact with the subject?"
        )
        self._log_step("first_message_gate", "yes" if send_first else "no")

        if send_first:
            try:
                current = self.registry.get_subject(subject_id)
                if current is None:
                    raise KeyError(f"Subject '{subject_id}' not found.")
                background_path = current.relic_subject_home / "gumi_background_profile.json"
                background = json.loads(background_path.read_text(encoding="utf-8"))
                composer = InitialContactComposer()
                calibration = _calibration_from_baseline(
                    relational_expectations, interaction_preferences, researcher_coded_fields
                )
                message_text, contact_event = composer.compose(
                    subject_profile=current.to_dict(),
                    gumi_background=background.get("domains", {}),
                    calibration=calibration,
                    language="it",
                )

                # First contact controls loop
                action = "preview"
                while True:
                    fcc_result = run_first_contact_controls(
                        self.io_in,
                        self.io_out,
                        ctx={
                            "profile_dir": str(current.relic_subject_home),
                            "delivery_config": delivery_config,
                            "message_text": message_text,
                        },
                    )
                    action = fcc_result.get("action", "preview")
                    self._log_step("first_contact_action", action)

                    if action == "regenerate":
                        new_composer = InitialContactComposer()
                        message_text, contact_event = new_composer.compose(
                            subject_profile=current.to_dict(),
                            gumi_background=background.get("domains", {}),
                            calibration=calibration,
                            language="it",
                        )
                        composer = new_composer
                        continue

                    if action == "edit":
                        message_text = fcc_result.get("payload", {}).get(
                            "message_text", message_text
                        )
                        continue

                    break  # preview, block, dry_run, send

                if action != "block":
                    if action == "dry_run":
                        contact_event = composer.send_dry_run(contact_event)
                    composer.log_event(contact_event, current.relic_subject_home)
                    if (
                        current.status == "hermes_profile_provisioned"
                        and contact_event.status in ("composed", "sent")
                    ):
                        profile = self.registry.mark_intro_composed(subject_id)
                    self._log_step("intro_composed", contact_event.status)

            except Exception as exc:
                self._log_step("intro_composed_failed", str(exc))

        profile = self.registry.get_subject(subject_id) or profile

        self._print(f"\nCreated profile: {profile.subject_id}")
        self._print(f"Status: {profile.status}")
        self._print(f"Version: {profile.profile_version}")
        self._print("\nBootstrap complete.")

        return profile

    def run_edit(self, subject_id: str) -> SubjectProfile:
        """Run the editing wizard for an existing subject."""
        profile = self.registry.get_subject(subject_id)
        if profile is None:
            raise KeyError(f"Subject '{subject_id}' not found.")

        self._edit_log_path = profile.relic_subject_home / "profile_edit_log.jsonl"
        self._edit_log_path.parent.mkdir(parents=True, exist_ok=True)

        self._print("\n=== Edit Subject Profile ===\n")

        self._print("Current State:")
        self._print(f"  Subject ID:    {profile.subject_id}")
        self._print(f"  Experiment ID: {profile.experiment_id}")
        self._print(f"  Status:        {profile.status}")
        self._print(f"  Version:       {profile.profile_version}")
        self._print(f"  Hermes:        {profile.hermes_profile_name}")
        self._print(f"  Created:       {profile.created_at}")
        self._print(f"  Updated:       {profile.updated_at}")
        self._print("")

        from relic.profile.registry import _FORWARD_TRANSITIONS

        allowed = _FORWARD_TRANSITIONS.get(profile.status, [])
        self._print("Available status transitions:")
        if allowed:
            for s in allowed:
                self._print(f"  - {s}")
        else:
            self._print("  (none)")
        self._print("")

        new_status = self._prompt(
            f"New status (current: {profile.status})", default=profile.status
        )

        if not new_status or new_status == profile.status:
            self._print("No status change.")
            return profile

        try:
            profile = self.registry.update_status(subject_id, new_status)
            self._log_edit_step("status_changed", new_status)
            self._print(f"\nStatus updated to: {profile.status}")
            self._print(f"New version: {profile.profile_version}")
        except ValueError as e:
            self._print(f"Error: {e}")
            return profile

        self._print("\nEdit complete.")
        return profile
