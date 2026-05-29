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
from relic.profile.baseline_artifact import build_baseline_artifact, write_baseline_artifact
from relic.profile._bootstrap_steps.item_battery import (
    battery_to_baseline_sections,
    collect_item_battery,
)
from relic.profile._bootstrap_steps.boundaries import collect_boundaries
from relic.profile._bootstrap_steps.consent import collect_consent_record
from relic.profile._bootstrap_steps.delivery_config import collect_delivery_config, collect_gemini_api_key
from relic.profile._bootstrap_steps.gumi_review import review_gumi_background
from relic.profile._bootstrap_steps.gumi_overrides import collect_gumi_overrides
from relic.profile._bootstrap_steps.first_contact_controls import run_first_contact_controls
from relic.profile._bootstrap_steps.self_report import collect_self_report_fields
from relic.profile._bootstrap_steps.researcher_coded import collect_researcher_coded_fields
from relic.profile._bootstrap_steps.interaction_prefs import collect_interaction_preferences
from relic.profile._bootstrap_steps.relational_expectations import collect_relational_expectations
from relic.gumi_plugin.cron_wiring import _normalize_hhmm, provision_for_subject
from relic.cli import start_hermes_gateway_for_profile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



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
        """Print a question and read user input, applying default if empty or on EOF."""
        prompt_text = question
        if default is not None:
            prompt_text = f"{question} [{default}]"
        print(prompt_text, file=self.io_out)

        if hasattr(self.io_in, "read"):
            try:
                raw = self.io_in.readline()
                if raw is None:
                    raw = ""
            except (EOFError, OSError):
                raw = ""
        else:
            try:
                raw = input()
            except (EOFError, KeyboardInterrupt):
                raw = ""

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

        # Check if subject already exists (before collecting any data)
        existing = self.registry.get_subject(subject_id)
        if existing is not None:
            self._print(f"\nSubject '{subject_id}' already exists!")
            self._print(f"  Status: {existing.status}")
            self._print(f"  Hermes: {existing.hermes_profile_name}")
            self._print("")
            choice = self._prompt("Choose: [U]pdate existing / [N]ew subject ID / [Q]uit", default="Q")
            choice = choice.lower().strip()
            if choice in ("u", "update", "edit"):
                self._print("\nOpening edit mode for existing subject...")
                return self.run_edit(subject_id)
            elif choice in ("n", "new"):
                self._print("\nEnter a new subject ID:")
                return self.run_init()
            else:
                self._print("\nAborted.")
                return existing

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

        # Step 3a: Self-report descriptive fields (name, age, gender, language, timezone, etc.)
        self._print("\n--- Subject Self-Report ---")
        sr_extra = collect_self_report_fields(self.io_in, self.io_out)
        self_report_fields.update(sr_extra)

        # Step 3b-rc: Optional researcher-coded overrides for battery-derived values.
        apply_researcher_coded_overrides = self._confirm(
            "Set researcher-coded overrides? (otherwise battery-derived values are kept)"
        )
        if apply_researcher_coded_overrides:
            self._print("\n--- Researcher-Coded Fields ---")
            rc_extra = collect_researcher_coded_fields(self.io_in, self.io_out)
            researcher_coded_fields.update(rc_extra)
            researcher_coded_overrides_origin = "applied_researcher_coded_overrides"
        else:
            rc_extra = {}
            researcher_coded_overrides_origin = "skipped_keep_battery_derived"
            self._print("Keeping battery-derived researcher-coded values.")

        # Step 3b-ip: Interaction preferences (message length, emoji, timing, topics)
        self._print("\n--- Interaction Preferences ---")
        ip_extra = collect_interaction_preferences(self.io_in, self.io_out)
        interaction_preferences.update(ip_extra)

        # Step 3b-re: Relational expectations (tone, continuity, disclosure, role)
        self._print("\n--- Relational Expectations ---")
        re_extra = collect_relational_expectations(self.io_in, self.io_out)
        relational_expectations.update(re_extra)

        # Step 3b: Boundaries, opt-out categories, risk flags
        boundaries_data = collect_boundaries(self.io_in, self.io_out)

        # Step 3g: Consent record
        consent_record = collect_consent_record(self.io_in, self.io_out)

        # Step 4: Gumi generation mode — always hybrid; structured battery already provides
        # all calibration inputs. Optional domain overrides remain available.
        gumi_mode = "hybrid"
        gumi_overrides, gumi_name, gumi_signature_emoji = collect_gumi_overrides(self.io_in, self.io_out, mode=gumi_mode)

        # Step 5: Hermes provisioning
        self._print("\n--- Hermes Provisioning ---")
        hermes_provision = self._confirm("Do you want to provision a Hermes profile?")
        hermes_value = "yes" if hermes_provision else "no"

        # Step 5b: Delivery configuration (gated by consent.delivery)

        # Scan existing subjects for reusable API keys (QoL: avoid re-entering)
        from relic.profile._bootstrap_steps.delivery_config import scan_existing_api_keys
        existing_keys = scan_existing_api_keys(self.registry)

        # Step 5c: Gemini API Key (if any media consent is True)
        gemini_key = ""
        if consent_record.get("generated_images") or consent_record.get("generated_audio") or consent_record.get("generated_music"):
            gemini_key = collect_gemini_api_key(self.io_in, self.io_out, existing_keys=existing_keys)
            self._log_step("gemini_api_key", "provided" if gemini_key else "skipped")
        delivery_config = collect_delivery_config(self.io_in, self.io_out, consent_record, subject_id=subject_id, existing_keys=existing_keys)

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
        self._log_step("self_report_extra_collected", str(len(sr_extra)))
        self._log_step("researcher_coded_overrides", researcher_coded_overrides_origin)
        self._log_step("researcher_coded_fields_collected", str(len(researcher_coded_fields)))
        self._log_step("researcher_coded_extra_collected", str(len(rc_extra)))
        self._log_step("interaction_preferences_collected", str(len(interaction_preferences)))
        self._log_step("interaction_preferences_extra_collected", str(len(ip_extra)))
        self._log_step("relational_expectations_collected", str(len(relational_expectations)))
        self._log_step("relational_expectations_extra_collected", str(len(re_extra)))
        self._log_step("boundaries_collected", str(len(boundaries_data)))
        self._log_step("consent_collected", "yes")
        self._log_step("gumi_mode_selected", gumi_mode)
        self._log_step("gumi_name", gumi_name)
        self._log_step("gumi_overrides_collected", str(len(gumi_overrides)))
        self._log_step("hermes_provisioning", hermes_value)
        self._log_step("delivery_config_collected", "yes" if delivery_config.get("delivery_enabled") else "no")

        # Persist delivery_config immediately so telegram_user_id survives hermes failures
        (profile.relic_subject_home / "delivery_config_draft.json").write_text(
            json.dumps(delivery_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

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
                # Persist signature_emoji into the background profile
                if gumi_signature_emoji:
                    gumi_profile_dict["signature_emoji"] = gumi_signature_emoji
                    background_path.write_text(
                        json.dumps(gumi_profile_dict, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
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
            "delivery_config": delivery_config,
            "boundaries": boundaries_data.get("boundaries", {}),
            "opt_out_categories": boundaries_data.get(
                "opt_out_categories", {"values": [], "origin": "subject-stated"}
            ),
            "risk_flags": boundaries_data.get("risk_flags", []),
            "escalation_contacts": boundaries_data.get("escalation_contacts", []),
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
                if current is not None and current.status == "baseline_complete":
                    current = self.registry.update_status(subject_id, "gumi_seed_generated")
                    self._log_step("gumi_seed_generated_auto", current.status)
                current = self.registry.get_subject(subject_id)
                if current is not None and current.status == "gumi_seed_generated":
                    profile = self.registry.update_status(subject_id, "gumi_seed_reviewed")
                    self._log_step("gumi_seed_reviewed", profile.status)
                # B3: pass agent_name so SOUL.md is generated with the correct name
                profile, _ = self.registry.provision_hermes_profile(subject_id, agent_name=gumi_name)
                self._log_step("hermes_profile_provisioned", str(profile.hermes_home))

                # Start Hermes gateway for this profile and wait until ready
                self._print(f"\n--- Hermes Gateway ---")
                gateway_ok = start_hermes_gateway_for_profile(
                    profile.hermes_profile_name, timeout_seconds=30
                )
                self._log_step("hermes_gateway_started", "ok" if gateway_ok else "warn")

                # WIRE04: provision no-agent cron jobs (checkin, followup, proactivity)
                try:
                    gumi_instance_id = f"gumi-{subject_id}"
                    hermes_profile_id = profile.hermes_profile_name
                    cron_result = provision_for_subject(
                        subject_id=subject_id,
                        gumi_instance_id=gumi_instance_id,
                        hermes_profile_id=hermes_profile_id,
                        schedule="*/30 * * * *",
                        dry_run=False,
                        hermes_home=str(profile.hermes_home),
                    )
                    self._log_step("no_agent_cron_provisioned", str(list(cron_result.get("scripts", {}).keys())))
                except Exception as exc:
                    self._log_step("no_agent_cron_provisioning_failed", str(exc))

                # B1: wire Telegram delivery if consent given and config collected
                telegram_user_id = delivery_config.get("telegram_user_id", "")
                telegram_bot_token_env = delivery_config.get("bot_token_env", "")
                if (
                    consent_record.get("delivery")
                    and telegram_user_id
                    and telegram_bot_token_env
                ):
                    try:
                        quiet_start = delivery_config.get("quiet_hours", {}).get("start", "22:00")
                        quiet_end = delivery_config.get("quiet_hours", {}).get("end", "08:00")
                        delivery_windows = delivery_config.get("delivery_windows") or [
                            {"start": "09:00", "end": "11:00"},
                            {"start": "19:00", "end": "21:00"},
                        ]
                        self.registry.configure_telegram_delivery(
                            subject_id=subject_id,
                            telegram_bot_token_env=telegram_bot_token_env,
                            telegram_user_id=telegram_user_id,
                            quiet_hours={
                                "start": _normalize_hhmm(quiet_start),
                                "end": _normalize_hhmm(quiet_end),
                                "timezone": delivery_config.get("timezone", "Europe/Rome"),
                            },
                            delivery_windows=delivery_windows,
                            timezone=delivery_config.get("timezone", "Europe/Rome"),
                            consent_for_active_elicitation=consent_record.get("active_elicitation", False),
                            consent_for_generated_images=consent_record.get("generated_images", False),
                            consent_for_generated_audio=consent_record.get("generated_audio", False),
                            consent_for_generated_music=consent_record.get("generated_music", False),
                            escalation_contacts=boundaries_data.get("escalation_contacts", []),
                        )
                        self._log_step("delivery_configured", "telegram")

                        # Write GEMINI_API_KEY to .env if provided
                        if gemini_key:
                            env_path = profile.hermes_home / ".env"
                            _upsert_env_var(env_path, "GEMINI_API_KEY", gemini_key)
                    except Exception as exc:
                        self._log_step("delivery_config_failed", str(exc))

                # B4: provision media canon (visual, voice, Lyria) if any media consent
                media_consent = any(
                    consent_record.get(k)
                    for k in ("generated_images", "generated_audio", "generated_music")
                )
                if media_consent:
                    try:
                        self._print("\n--- Media Identity ---")
                        self._print("Generating visual canon, voice profile, and Lyria signature...")
                        import os as _os
                        if gemini_key:
                            _os.environ["GEMINI_API_KEY"] = gemini_key
                        self.registry.generate_gumi_media_canon(subject_id)
                        self._log_step("media_canon_provisioned", "ok")
                        self._print("Media identity provisioned.")
                    except Exception as exc:
                        self._log_step("media_canon_provisioning_failed", str(exc))
                        self._print(f"[warn] Media identity provisioning failed: {exc}")

                # B2: provision cron specs — maintenance always, initiative if delivery configured,
                # media if any generated-content consent granted
                try:
                    cron_families = ["maintenance"]
                    delivery_policy_path = profile.relic_subject_home / "delivery_policy.json"
                    if delivery_policy_path.exists():
                        # Initiative (check-in), diegetic fragments and proactive
                        # re-engagement all require a configured delivery target.
                        cron_families.append("initiative")
                        cron_families.append("diegetic")
                        cron_families.append("proactive")
                    if any(consent_record.get(k) for k in ("generated_images", "generated_audio", "generated_music")):
                        cron_families.append("media")
                    self.registry.provision_subject_cron_specs(
                        subject_id,
                        families=cron_families,
                        dry_run=False,
                        diegetic_deliver_target="telegram",
                        proactive_deliver_target="telegram",
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
                delivery_enabled = bool(delivery_config.get("delivery_enabled"))
                if delivery_enabled:
                    self._print("\nInvia il primo messaggio tramite Hermes? Gumi lo genererà e invierà via Telegram. [s]end / [b]lock")
                    raw = self.io_in.readline()
                    choice = raw.strip().lower() if raw else "block"
                    action = "send" if choice in ("s", "send") else "block"
                else:
                    self._print("\nDelivery non configurato — primo messaggio non inviato.")
                    action = "block"

                self._log_step("first_contact_action", action)

                if action == "send":
                    import os as _os
                    _os.environ.setdefault("RELIC_ALLOW_LIVE_DELIVERY", "1")
                    try:
                        self.registry.dispatch_intro_via_hermes(subject_id)
                        profile = self.registry.mark_intro_composed(subject_id)
                        profile = self.registry.mark_intro_sent(subject_id)
                        profile = self.registry.update_status(subject_id, "active")
                        self._log_step("intro_dispatched_via_hermes", "scheduled")
                        self._print("\nPrimo messaggio affidato a Hermes (invio entro ~1 min).")
                    except Exception as send_exc:
                        self._log_step("intro_dispatch_failed", str(send_exc))
                        self._print(f"\n[warn] Dispatch fallito: {send_exc}")

            except Exception as exc:
                self._log_step("intro_composed_failed", str(exc))

        profile = self.registry.get_subject(subject_id) or profile

        self._print(f"\nCreated profile: {profile.subject_id}")
        self._print(f"Status: {profile.status}")
        self._print(f"Version: {profile.profile_version}")
        self._print("\nBootstrap complete.")
        self._print("\n--- Final Summary ---")
        self._print(f"Subject artifacts directory: {profile.relic_subject_home}")
        self._print("Researcher-editable files:")
        self._print("  - subject_baseline.json")
        self._print("  - boundary_policy.json")
        self._print("  - item_battery_response.json")
        self._print(
            f"Manual edits require re-provision: relic subject reprovision {profile.subject_id}"
        )

        return profile

    def _detect_incomplete_baseline(self, profile: SubjectProfile) -> list[str]:
        """Return list of baseline sections missing fields added after initial bootstrap."""
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        if not baseline_path.exists():
            return []
        try:
            bl = json.loads(baseline_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        missing = []
        sr = bl.get("self_report_fields", {})
        rc = bl.get("researcher_coded_fields", {})
        re_ = bl.get("relational_expectations", {})
        bg_path = profile.relic_subject_home / "gumi_background_profile.json"
        bg_display_name = None
        if bg_path.exists():
            try:
                bg = json.loads(bg_path.read_text(encoding="utf-8"))
                bg_display_name = bg.get("display_name")
            except Exception:
                pass

        sr_new_fields = [
            "preferred_name", "age_range", "gender_identity", "preferred_pronoun",
            "language", "occupation_or_study", "location", "family_structure",
            "narrative_self_description", "contact_channel_preference",
        ]
        if any(f not in sr for f in sr_new_fields):
            missing.append("self_report_fields (campi mancanti post-TUI)")

        rc_new_fields = ["attachment_style", "affect_regulation_notes", "cultural_context_notes"]
        if any(f not in rc for f in rc_new_fields):
            missing.append("researcher_coded_fields (campi mancanti post-TUI)")

        re_new_fields = [
            "desired_relationship_tone", "continuity_expectations",
            "disclosure_comfort_level", "role_expectations_for_gumi",
        ]
        if any(f not in re_ for f in re_new_fields):
            missing.append("relational_expectations (campi mancanti post-TUI)")

        if bg_display_name is None:
            missing.append("gumi_background_profile.display_name (agent_name non impostato)")

        # Check if background was generated without LLM (model_used=None in provenance)
        provenance_path = profile.relic_subject_home / "provenance" / "gumi_generation_report.json"
        if provenance_path.exists():
            try:
                prov = json.loads(provenance_path.read_text(encoding="utf-8"))
                if prov.get("model_used") is None:
                    missing.append("gumi_background_profile (generato senza LLM — calibrazione incompleta)")
            except Exception:
                pass

        return missing

    def _reprovision_baseline_fields(self, profile: SubjectProfile) -> bool:
        """Re-collect baseline fields missing due to TUI changes, merge into existing baseline.

        Returns True if baseline was updated and background should be regenerated.
        """
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        bl = json.loads(baseline_path.read_text(encoding="utf-8"))

        self._print("\n--- Raccolta campi baseline mancanti ---")
        self._print("Rispondere ai campi aggiunti dopo il bootstrap iniziale.")
        self._print("Lasciare vuoto per saltare un campo.\n")

        updated = False

        # self_report_fields
        sr = bl.get("self_report_fields", {})
        sr_new_fields = [
            "preferred_name", "age_range", "gender_identity", "preferred_pronoun",
            "language", "occupation_or_study", "location", "family_structure",
            "narrative_self_description", "contact_channel_preference",
        ]
        if any(f not in sr for f in sr_new_fields):
            self._print("--- Self Report ---")
            new_sr = collect_self_report_fields(self.io_in, self.io_out)
            for k, v in new_sr.items():
                if k not in sr and v not in (None, "", {}):
                    sr[k] = v
                    updated = True
            bl["self_report_fields"] = sr

        # researcher_coded_fields
        rc = bl.get("researcher_coded_fields", {})
        rc_new_fields = ["attachment_style", "affect_regulation_notes", "cultural_context_notes"]
        if any(f not in rc for f in rc_new_fields):
            self._print("--- Researcher Coded Fields ---")
            new_rc = collect_researcher_coded_fields(self.io_in, self.io_out)
            for k, v in new_rc.items():
                if k not in rc and v not in (None, "", {}):
                    rc[k] = v
                    updated = True
            bl["researcher_coded_fields"] = rc

        # relational_expectations
        re_ = bl.get("relational_expectations", {})
        re_new_fields = [
            "desired_relationship_tone", "continuity_expectations",
            "disclosure_comfort_level", "role_expectations_for_gumi",
        ]
        if any(f not in re_ for f in re_new_fields):
            self._print("--- Relational Expectations ---")
            new_re = collect_relational_expectations(self.io_in, self.io_out)
            for k, v in new_re.items():
                if k not in re_ and v not in (None, "", {}):
                    re_[k] = v
                    updated = True
            bl["relational_expectations"] = re_

        if updated:
            # bump version_history
            vh = bl.get("version_history", [])
            vh.append({
                "version": len(vh) + 1,
                "edited_at": _now_iso(),
                "edited_by": bl.get("researcher_id", ""),
                "fields_changed": ["baseline_reprovision_post_tui_update"],
                "edit_mode": "reprovision",
                "change_summary": "re-collected fields missing from initial bootstrap (TUI update)",
            })
            bl["version_history"] = vh
            baseline_path.write_text(json.dumps(bl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self._print("  Baseline aggiornato.")
            self._log_edit_step("baseline_fields_reprovisioned", "ok")

        return updated

    def _reprovision_gumi_identity(self, profile: SubjectProfile, subject_id: str) -> None:
        """Regenerate gumi_background_profile from updated baseline, fix display_name, regenerate SOUL/world."""
        import os as _os

        self._print("\n--- Gumi Identity ---")

        # Collect agent name + signature emoji
        _, agent_name, signature_emoji = collect_gumi_overrides(
            self.io_in, self.io_out, mode="random"
        )
        if not agent_name:
            agent_name = "Gumi"

        # Regenerate full background from updated baseline (force bypasses status check)
        self._print("  Rigenerazione background Gumi dal baseline aggiornato...")
        try:
            _, paths = self.registry.generate_gumi_background(
                subject_id, mode="hybrid", force=True
            )
            self._print("  Background rigenerato.")
            self._log_edit_step("gumi_background_regenerated", "ok")
        except Exception as exc:
            self._print(f"  [warn] Rigenerazione background fallita: {exc}")
            self._log_edit_step("gumi_background_regeneration_failed", str(exc))

        # Patch display_name + signature_emoji
        bg_path = profile.relic_subject_home / "gumi_background_profile.json"
        if not bg_path.exists():
            self._print("  [warn] gumi_background_profile.json mancante dopo rigenerazione.")
            return
        bg = json.loads(bg_path.read_text(encoding="utf-8"))
        bg["display_name"] = agent_name
        bg["agent_name"] = agent_name
        if signature_emoji:
            bg["signature_emoji"] = signature_emoji
        bg_path.write_text(json.dumps(bg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ws_bg = profile.hermes_home / "workspace" / "gumi" / "background.json"
        if ws_bg.parent.exists():
            ws_bg.write_text(json.dumps(bg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._log_edit_step("gumi_display_name_set", agent_name)
        self._print(f"  display_name impostato: {agent_name}")

        # Regenerate SOUL.md + world.md with new background
        self._print("  Rigenerazione SOUL.md e world.md...")
        try:
            ws = profile.hermes_home / "workspace" / "gumi"
            self.registry._generate_identity_files(
                profile=profile,
                agent_name=agent_name,
                background=bg,
                workspace=ws,
            )
            self._print("  SOUL.md e world.md rigenerati.")
            self._log_edit_step("gumi_identity_files_regenerated", "ok")
        except Exception as exc:
            self._print(f"  [warn] Rigenerazione identity files fallita: {exc}")
            self._log_edit_step("gumi_identity_files_regeneration_failed", str(exc))

    def _detect_missing_artifacts(self, profile: SubjectProfile) -> list[str]:
        """Return list of missing provisioning artifacts for an active subject."""
        missing = []
        sh = profile.relic_subject_home
        hh = profile.hermes_home
        ws = hh / "workspace" / "gumi"
        checks = [
            (sh / "gumi_background_profile.json", "gumi_background_profile"),
            (sh / "gumi_sweet_spot_config.json", "gumi_sweet_spot_config"),
            (sh / "baseline_user_profile.json", "baseline_user_profile"),
            (sh / "item_battery_response.json", "item_battery_response"),
            (sh / "consent_record.json", "consent_record"),
            (sh / "gumi_voice_canon.json", "gumi_voice_canon"),
            (sh / "gumi_visual_canon.json", "gumi_visual_canon"),
            (sh / "gumi_music_canon.json", "gumi_music_canon"),
            (ws / "world.md", "workspace/gumi/world.md (empty counts as missing)" if (ws / "world.md").exists() and (ws / "world.md").stat().st_size == 0 else "workspace/gumi/world.md"),
            (hh / "AVATAR_SPEC.md", "AVATAR_SPEC.md"),
        ]
        for path, label in checks:
            if not path.exists() or (path.suffix == ".md" and path.stat().st_size == 0):
                missing.append(label)
        vi_manifest = sh / "Visual_Identity" / "manifest.json"
        if not vi_manifest.exists():
            missing.append("Visual_Identity/manifest.json (anchor image)")
        return missing

    def run_reprovision(self, subject_id: str) -> SubjectProfile:
        """Re-run provisioning steps for an active subject with missing artifacts."""
        profile = self.registry.get_subject(subject_id)
        if profile is None:
            raise KeyError(f"Subject '{subject_id}' not found.")

        self._edit_log_path = profile.relic_subject_home / "profile_edit_log.jsonl"
        self._edit_log_path.parent.mkdir(parents=True, exist_ok=True)

        self._print(f"\n=== Re-provision Subject: {subject_id} ===\n")

        missing = self._detect_missing_artifacts(profile)
        incomplete = self._detect_incomplete_baseline(profile)

        if not missing and not incomplete:
            self._print("All artifacts present. Nothing to re-provision.")
            return profile

        if missing:
            self._print("Missing artifacts:")
            for m in missing:
                self._print(f"  - {m}")
            self._print("")

        # --- Baseline fields missing due to TUI changes ---
        if incomplete:
            self._print("Campi baseline incompleti (aggiunti dopo bootstrap iniziale):")
            for f in incomplete:
                self._print(f"  - {f}")
            self._print("")
            needs_identity = any(
                k in f for f in incomplete
                for k in ("display_name", "senza LLM")
            )
            if any("campi mancanti" in f for f in incomplete):
                if self._confirm("Raccogliere i campi baseline mancanti?"):
                    baseline_updated = self._reprovision_baseline_fields(profile)
                    needs_identity = needs_identity or baseline_updated
            if needs_identity:
                if self._confirm("Rigenerare identità Gumi (background, SOUL.md, world.md)?"):
                    self._reprovision_gumi_identity(profile, subject_id)
                    # Identity regenerated → force media canon refresh too
                    missing = list(missing) + ["voice_canon (dopo rigenerazione identità)"]

        # --- Identity files (world.md empty → regenerate via Ollama) ---
        ws = profile.hermes_home / "workspace" / "gumi"
        world_path = ws / "world.md"
        background_path = profile.relic_subject_home / "gumi_background_profile.json"

        needs_world = world_path.exists() and world_path.stat().st_size == 0
        if needs_world and background_path.exists():
            if self._confirm("world.md is empty. Regenerate via Ollama?"):
                try:
                    import os as _os
                    from relic.gumi.llm_narrator import GumiBuildContext, OllamaNarrator
                    background = json.loads(background_path.read_text(encoding="utf-8"))
                    agent_name = background.get("display_name", subject_id)
                    ctx = GumiBuildContext.from_background_and_personalization(
                        agent_name=agent_name, background=background
                    )
                    ollama_endpoint = _os.environ.get("RELIC_OLLAMA_ENDPOINT", "http://localhost:11434/v1")
                    ollama_model = _os.environ.get("RELIC_OLLAMA_MODEL", "gemma4:31b-cloud")
                    narrator = OllamaNarrator(endpoint=ollama_endpoint, model=ollama_model)
                    if narrator.is_available():
                        world_text = narrator.generate_world_md(ctx)
                        self._print("  Generated world.md via Ollama.")
                    else:
                        world_text = narrator.fallback_world_md(ctx)
                        self._print("  Ollama unavailable — using template fallback.")
                    ws.mkdir(parents=True, exist_ok=True)
                    world_path.write_text(world_text, encoding="utf-8")
                    (profile.relic_subject_home / "gumi_world.md").write_text(world_text, encoding="utf-8")
                    self._log_edit_step("world_md_regenerated", "ok")
                except Exception as exc:
                    self._print(f"  [warn] world.md regeneration failed: {exc}")

        # --- Media canon (visual, voice, Lyria, anchor image) ---
        needs_media = any(
            m for m in missing
            if any(k in m for k in ("voice_canon", "visual_canon", "music_canon", "AVATAR_SPEC", "Visual_Identity"))
        )
        if needs_media:
            if self._confirm("Provision media identity (voice, visual canon, anchor image)?"):
                import os as _os
                # Read existing key from .env or env
                env_path = profile.hermes_home / ".env"
                gemini_key = _os.environ.get("GEMINI_API_KEY", "") or _read_env_var(env_path, "GEMINI_API_KEY")
                if not gemini_key:
                    if self._confirm("Provide Gemini API key for anchor image generation?"):
                        gemini_key = self._prompt("GEMINI_API_KEY", default="").strip()
                try:
                    if gemini_key:
                        _os.environ["GEMINI_API_KEY"] = gemini_key
                        _upsert_env_var(env_path, "GEMINI_API_KEY", gemini_key)
                    self.registry.generate_gumi_media_canon(subject_id)
                    self._log_edit_step("media_canon_reprovisioned", "ok")
                    self._print("  Media identity provisioned.")
                except Exception as exc:
                    self._log_edit_step("media_canon_reprovisioning_failed", str(exc))
                    self._print(f"  [warn] Media identity failed: {exc}")

        profile = self.registry.get_subject(subject_id) or profile
        self._print(f"\nRe-provision complete. Status: {profile.status}")
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

        # Detect missing artifacts for active subjects and offer re-provision
        missing = self._detect_missing_artifacts(profile)
        if missing:
            self._print(f"  [!] {len(missing)} artifact(s) missing — run `relic subject reprovision {subject_id}` to complete.")
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


def _read_env_var(env_path: Path, key: str) -> str:
    """Read a single variable from .env file, return empty string if not found."""
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.strip()[len(key) + 1:]
    return ""


def _upsert_env_var(env_path: Path, key: str, value: str) -> None:
    """Update or append a single line in .env file."""
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    
    if not updated:
        new_lines.append(f"{key}={value}")
    
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
