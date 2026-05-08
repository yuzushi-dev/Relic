"""Profile management CLI for multi-subject Relic registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from relic.profile.registry import ProfileRegistry, VALID_STATES


def profile_main(argv: list[str] | None = None) -> int:
    """Entry point for the `relic profile` subcommand."""
    parser = argparse.ArgumentParser(
        prog="relic profile",
        description="Multi-subject profile registry for Relic.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    # relic profile list
    subparsers.add_parser("list", help="List all subjects in the registry.")

    # relic profile show <subject_id>
    show_parser = subparsers.add_parser("show", help="Show a subject profile.")
    show_parser.add_argument("subject_id", help="Subject identifier.")

    # relic profile init [--subject-id <id>] [--experiment-id <id>]
    init_parser = subparsers.add_parser("init", help="Initialize a new subject profile.")
    init_parser.add_argument("--subject-id", default=None, help="Subject identifier (auto-generated if omitted).")
    init_parser.add_argument("--experiment-id", default=None, help="Experiment identifier.")
    init_parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch the interactive TUI wizard for guided bootstrap.",
    )

    # relic profile edit <subject_id>
    edit_parser = subparsers.add_parser("edit", help="Edit a subject profile.")
    edit_parser.add_argument("subject_id", help="Subject identifier.")
    edit_parser.add_argument(
        "--status",
        choices=VALID_STATES,
        help="New status for the subject.",
    )
    edit_parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch the interactive TUI wizard for guided editing.",
    )

    # relic profile validate <subject_id>
    validate_parser = subparsers.add_parser("validate", help="Validate a subject profile.")
    validate_parser.add_argument("subject_id", help="Subject identifier.")

    # relic profile bootstrap ...
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Resume or validate PR28 bootstrap outputs.")
    bootstrap_subparsers = bootstrap_parser.add_subparsers(dest="bootstrap_action", required=True)
    bootstrap_resume = bootstrap_subparsers.add_parser("resume", help="Show a bootstrap session checkpoint summary.")
    bootstrap_resume.add_argument("bootstrap_session_id", help="Bootstrap session identifier.")
    bootstrap_validate = bootstrap_subparsers.add_parser("validate", help="Validate PR28 bootstrap outputs for a subject.")
    bootstrap_validate.add_argument("subject_id", help="Subject identifier.")

    # relic profile export <subject_id> --redacted --out <path>
    export_parser = subparsers.add_parser("export", help="Export a subject profile.")
    export_parser.add_argument("subject_id", help="Subject identifier.")
    export_parser.add_argument(
        "--redacted",
        action="store_true",
        help="Redact sensitive fields before export.",
    )
    export_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output file path.",
    )

    # relic profile archive <subject_id>
    archive_parser = subparsers.add_parser("archive", help="Archive a subject profile.")
    archive_parser.add_argument("subject_id", help="Subject identifier.")

    # relic profile gumi ...
    gumi_parser = subparsers.add_parser("gumi", help="Manage subject-specific Gumi bootstrap.")
    gumi_subparsers = gumi_parser.add_subparsers(dest="gumi_action", required=True)

    gumi_generate = gumi_subparsers.add_parser("generate", help="Generate a Gumi background profile.")
    gumi_generate.add_argument("subject_id", help="Subject identifier.")
    gumi_generate.add_argument(
        "--mode",
        choices=("random", "manual", "hybrid"),
        required=True,
        help="Generation mode.",
    )
    gumi_generate.add_argument("--seed", type=int, default=None, help="Deterministic random seed.")

    gumi_intro = gumi_subparsers.add_parser("intro", help="Compose or send Gumi's first contact.")
    gumi_intro_subparsers = gumi_intro.add_subparsers(dest="intro_action", required=True)
    intro_compose = gumi_intro_subparsers.add_parser("compose", help="Compose first contact locally.")
    intro_compose.add_argument("subject_id", help="Subject identifier.")
    intro_compose.add_argument("--seed", type=int, default=None, help="Deterministic message seed.")
    intro_compose.add_argument("--language", default="it", choices=("it", "en"), help="Message language.")
    intro_send = gumi_intro_subparsers.add_parser("send", help="Send or dry-run first contact.")
    intro_send.add_argument("subject_id", help="Subject identifier.")
    send_mode = intro_send.add_mutually_exclusive_group(required=True)
    send_mode.add_argument("--dry-run", action="store_true", help="Mark as sent without live delivery.")
    send_mode.add_argument("--deliver", action="store_true", help="Use a live delivery provider.")
    intro_send.add_argument(
        "--live",
        action="store_true",
        help="Actually invoke Hermes delivery. Requires RELIC_ALLOW_LIVE_DELIVERY=1.",
    )

    gumi_media = gumi_subparsers.add_parser("media", help="Manage Gumi visual, voice, and Lyria canons.")
    gumi_media_subparsers = gumi_media.add_subparsers(dest="media_action", required=True)
    media_generate = gumi_media_subparsers.add_parser("generate", help="Generate local media canons.")
    media_generate.add_argument("subject_id", help="Subject identifier.")
    media_generate.add_argument("--mode", default="hybrid", choices=("hybrid", "constraints"), help="Canon generation mode.")
    media_generate.add_argument("--seed", type=int, default=None, help="Deterministic media canon seed.")
    media_show = gumi_media_subparsers.add_parser("show", help="Show existing media canons.")
    media_show.add_argument("subject_id", help="Subject identifier.")

    # relic profile hermes ...
    hermes_parser = subparsers.add_parser("hermes", help="Manage subject-specific Hermes profile.")
    hermes_subparsers = hermes_parser.add_subparsers(dest="hermes_action", required=True)
    hermes_provision = hermes_subparsers.add_parser("provision", help="Provision a private Gumi Hermes profile.")
    hermes_provision.add_argument("subject_id", help="Subject identifier.")
    hermes_show = hermes_subparsers.add_parser("show", help="Show private Hermes profile status.")
    hermes_show.add_argument("subject_id", help="Subject identifier.")

    hermes_telegram = hermes_subparsers.add_parser(
        "configure-telegram", help="Configure private Telegram delivery settings."
    )
    hermes_telegram.add_argument("subject_id", help="Subject identifier.")
    hermes_telegram.add_argument("--bot-token-env", required=True, help="Env var name for Telegram bot token.")
    hermes_telegram.add_argument("--telegram-user-id", required=True, help="Telegram user or chat id.")
    hermes_telegram.add_argument("--quiet-hours", default="22:00-08:00", help="Quiet hours window.")
    hermes_telegram.add_argument("--maximum-contact-frequency", default="1/day", help="Maximum contact frequency.")
    hermes_telegram.add_argument("--consent-images", action="store_true", help="Consent for generated images.")
    hermes_telegram.add_argument("--consent-audio", action="store_true", help="Consent for generated audio.")
    hermes_telegram.add_argument("--consent-music", action="store_true", help="Consent for generated music.")

    hermes_cron = hermes_subparsers.add_parser("cron", help="Provision subject-specific cron specs.")
    hermes_cron_subparsers = hermes_cron.add_subparsers(dest="cron_action", required=True)
    hermes_cron_provision = hermes_cron_subparsers.add_parser("provision", help="Provision cron specs.")
    hermes_cron_provision.add_argument("subject_id", help="Subject identifier.")
    hermes_cron_provision.add_argument("--maintenance", action="store_true", help="Include maintenance cron family.")
    hermes_cron_provision.add_argument("--initiative", action="store_true", help="Include initiative cron family.")
    hermes_cron_provision.add_argument("--media", action="store_true", help="Include media cron family.")
    hermes_cron_provision.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    hermes_cron_provision.add_argument("--apply", action="store_true", help="Apply cron specs.")
    hermes_cron_list = hermes_cron_subparsers.add_parser("list", help="List subject cron manifest.")
    hermes_cron_list.add_argument("subject_id", help="Subject identifier.")
    hermes_cron_validate = hermes_cron_subparsers.add_parser("validate", help="Validate subject cron manifest.")
    hermes_cron_validate.add_argument("subject_id", help="Subject identifier.")

    args = parser.parse_args(argv)

    registry = ProfileRegistry()

    try:
        if args.action == "list":
            subjects = registry.list_subjects()
            if not subjects:
                print("No subjects found.")
                return 0
            for s in subjects:
                print(f"{s.subject_id}  [{s.status}]  exp={s.experiment_id}")
            return 0

        elif args.action == "show":
            profile = registry.get_subject(args.subject_id)
            if profile is None:
                print(f"Subject '{args.subject_id}' not found.", file=sys.stderr)
                return 1
            print(json.dumps(profile.to_dict(), indent=2))
            return 0

        elif args.action == "init":
            if args.tui:
                # Launch TUI wizard
                from relic.profile.bootstrap_tui import BootstrapTUI

                tui = BootstrapTUI(registry=registry)
                try:
                    profile = tui.run_init(
                        subject_id=args.subject_id,
                        experiment_id=args.experiment_id,
                    )
                    print(f"\nSubject '{profile.subject_id}' created successfully.")
                    print(f"Status: {profile.status}")
                    print(f"Location: {profile.relic_subject_home}")
                    return 0
                except Exception as e:
                    print(f"TUI Error: {e}", file=sys.stderr)
                    return 1

            # Non-TUI mode: simple creation
            subject_id = args.subject_id
            experiment_id = args.experiment_id
            if not subject_id:
                import uuid
                subject_id = f"subj_{uuid.uuid4().hex[:8]}"
            if not experiment_id:
                print("--experiment-id is required.", file=sys.stderr)
                return 1
            profile = registry.create_subject(subject_id, experiment_id)
            print(f"Created subject '{profile.subject_id}' with status '{profile.status}'.")
            return 0

        elif args.action == "edit":
            if args.tui:
                # Launch TUI wizard for editing
                from relic.profile.bootstrap_tui import BootstrapTUI

                tui = BootstrapTUI(registry=registry)
                try:
                    profile = tui.run_edit(args.subject_id)
                    print(f"\nSubject '{profile.subject_id}' updated successfully.")
                    print(f"Status: {profile.status}")
                    print(f"Version: {profile.profile_version}")
                    return 0
                except KeyError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    return 1
                except Exception as e:
                    print(f"TUI Error: {e}", file=sys.stderr)
                    return 1

            profile = registry.get_subject(args.subject_id)
            if profile is None:
                print(f"Subject '{args.subject_id}' not found.", file=sys.stderr)
                return 1
            if args.status:
                profile = registry.update_status(args.subject_id, args.status)
                print(f"Updated status to '{profile.status}'.")
            else:
                print(f"Current status: {profile.status}")
                print("Use --status <new_status> to transition.")
            return 0

        elif args.action == "validate":
            valid, errors = registry.validate_subject(args.subject_id)
            if valid:
                print(f"Subject '{args.subject_id}' is valid.")
                return 0
            print(f"Validation failed for '{args.subject_id}':", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

        elif args.action == "bootstrap":
            if args.bootstrap_action == "resume":
                from relic.bootstrap import resume_bootstrap_session

                payload = resume_bootstrap_session(registry.relic_home, args.bootstrap_session_id)
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0

            if args.bootstrap_action == "validate":
                from jsonschema import Draft7Validator

                from relic.bootstrap import OUTPUT_NAMES

                profile = registry.get_subject(args.subject_id)
                if profile is None:
                    print(f"Subject '{args.subject_id}' not found.", file=sys.stderr)
                    return 1
                errors: list[str] = []
                for name in OUTPUT_NAMES:
                    artifact_path = profile.relic_subject_home / f"{name}.json"
                    schema_path = Path("schemas") / "bootstrap" / f"{name}.schema.json"
                    if not artifact_path.is_file():
                        errors.append(f"Missing bootstrap artifact: {artifact_path.name}")
                        continue
                    if not schema_path.is_file():
                        errors.append(f"Missing bootstrap schema: {schema_path}")
                        continue
                    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    for err in Draft7Validator(schema).iter_errors(payload):
                        errors.append(f"{artifact_path.name}: {err.message}")
                if errors:
                    print(f"Bootstrap validation failed for '{args.subject_id}':", file=sys.stderr)
                    for err in errors:
                        print(f"  - {err}", file=sys.stderr)
                    return 1
                print(f"Bootstrap outputs for '{args.subject_id}' are valid.")
                return 0

        elif args.action == "export":
            if not args.redacted:
                print("--redacted is required for export.", file=sys.stderr)
                return 1
            out = registry.export_redacted(args.subject_id, args.out)
            print(f"Exported redacted profile to {out}")
            return 0

        elif args.action == "archive":
            profile = registry.archive_subject(args.subject_id)
            print(f"Archived subject '{profile.subject_id}' (status: {profile.status}).")
            return 0

        elif args.action == "gumi":
            if args.gumi_action == "generate":
                profile, paths = registry.generate_gumi_background(
                    args.subject_id,
                    mode=args.mode,
                    seed=args.seed,
                )
                print(f"Generated Gumi profile for '{profile.subject_id}'.")
                print(f"Status: {profile.status}")
                print(f"Background: {paths['background']}")
                return 0

            if args.gumi_action == "intro":
                from relic.gumi.initial_contact import (
                    CalibrationConfig,
                    ContactEvent,
                    InitialContactComposer,
                )

                profile = registry.get_subject(args.subject_id)
                if profile is None:
                    print(f"Subject '{args.subject_id}' not found.", file=sys.stderr)
                    return 1

                intro_path = profile.relic_subject_home / "gumi_intro_message.json"
                if args.intro_action == "compose":
                    background_path = profile.relic_subject_home / "gumi_background_profile.json"
                    if not background_path.exists():
                        print("Missing gumi_background_profile.json.", file=sys.stderr)
                        return 1
                    background = json.loads(background_path.read_text(encoding="utf-8"))
                    composer = InitialContactComposer(seed=args.seed)
                    message_text, event = composer.compose(
                        subject_profile=profile.to_dict(),
                        gumi_background=background.get("domains", {}),
                        calibration=CalibrationConfig(),
                        language=args.language,
                    )
                    if event.status == "blocked":
                        composer.log_event(event, profile.relic_subject_home)
                        print("Intro composition blocked by safety policy.", file=sys.stderr)
                        return 1
                    local_only = profile.relic_subject_home / "local_only"
                    local_only.mkdir(parents=True, exist_ok=True)
                    (local_only / f"{event.message_id}.txt").write_text(message_text, encoding="utf-8")
                    composer.log_event(event, profile.relic_subject_home)
                    updated = registry.mark_intro_composed(args.subject_id)
                    print(f"Composed intro for '{updated.subject_id}'.")
                    print(f"Status: {updated.status}")
                    print(f"Event: {intro_path}")
                    return 0

                if args.intro_action == "send":
                    if args.deliver:
                        decision = registry.prepare_intro_delivery(args.subject_id, live=args.live)
                        if args.live:
                            updated = registry.mark_intro_sent(args.subject_id)
                            print(f"Delivered intro for '{updated.subject_id}' via Hermes.")
                            print(f"Status: {updated.status}")
                            return 0
                        print(f"Prepared Hermes delivery for '{profile.subject_id}'.")
                        print(f"Target: {decision['target']}")
                        print("Use --live with RELIC_ALLOW_LIVE_DELIVERY=1 to send.")
                        return 0
                    if not intro_path.exists():
                        print("Missing gumi_intro_message.json.", file=sys.stderr)
                        return 1
                    event_data = json.loads(intro_path.read_text(encoding="utf-8"))
                    event = ContactEvent(**event_data)
                    composer = InitialContactComposer()
                    sent_event = composer.send_dry_run(event)
                    composer.log_event(sent_event, profile.relic_subject_home)
                    updated = registry.mark_intro_sent(args.subject_id)
                    print(f"Dry-run sent intro for '{updated.subject_id}'.")
                    print(f"Status: {updated.status}")
                    return 0

            if args.gumi_action == "media":
                profile = registry.get_subject(args.subject_id)
                if profile is None:
                    print(f"Subject '{args.subject_id}' not found.", file=sys.stderr)
                    return 1
                if args.media_action == "generate":
                    profile, _, paths = registry.generate_gumi_media_canon(args.subject_id, seed=args.seed)
                    print(f"Generated media canons for '{profile.subject_id}'.")
                    for name, path in paths.items():
                        print(f"{name}: {path}")
                    return 0
                if args.media_action == "show":
                    paths = {
                        "visual": profile.relic_subject_home / "gumi_visual_canon.json",
                        "voice": profile.relic_subject_home / "gumi_voice_canon.json",
                        "lyria": profile.relic_subject_home / "gumi_lyria_canon.json",
                        "policy": profile.relic_subject_home / "gumi_media_policy.json",
                    }
                    payload = {}
                    for name, path in paths.items():
                        if not path.exists():
                            print(f"Missing {path.name}.", file=sys.stderr)
                            return 1
                        payload[name] = json.loads(path.read_text(encoding="utf-8"))
                    print(json.dumps(payload, indent=2, ensure_ascii=False))
                    return 0

            parser.print_help()
            return 1

        elif args.action == "hermes":
            if args.hermes_action == "provision":
                profile, paths = registry.provision_hermes_profile(args.subject_id)
                print(f"Provisioned Hermes profile '{profile.hermes_profile_name}'.")
                print(f"Status: {profile.status}")
                print(f"Config: {paths['config']}")
                return 0
            if args.hermes_action == "show":
                print(json.dumps(registry.hermes_profile_status(args.subject_id), indent=2))
                return 0
            if args.hermes_action == "configure-telegram":
                _, policy = registry.configure_telegram_delivery(
                    args.subject_id,
                    telegram_bot_token_env=args.bot_token_env,
                    telegram_user_id=args.telegram_user_id,
                    quiet_hours=args.quiet_hours,
                    maximum_contact_frequency=args.maximum_contact_frequency,
                    consent_for_generated_images=args.consent_images,
                    consent_for_generated_audio=args.consent_audio,
                    consent_for_generated_music=args.consent_music,
                )
                print(json.dumps(policy.to_dict(), indent=2))
                return 0
            if args.hermes_action == "cron":
                if args.cron_action == "provision":
                    families = [family for family in ("maintenance", "initiative", "media") if getattr(args, family)]
                    if not families:
                        families = ["maintenance"]
                    profile, paths = registry.provision_subject_cron_specs(
                        args.subject_id,
                        families=families,
                        dry_run=args.dry_run or not args.apply,
                    )
                    print(f"Provisioned cron specs for '{profile.hermes_profile_name}'.")
                    for name, path in paths.items():
                        print(f"{name}: {path}")
                    return 0
                if args.cron_action == "list":
                    manifest = registry.get_subject(args.subject_id)
                    if manifest is None:
                        print(f"Subject '{args.subject_id}' not found.", file=sys.stderr)
                        return 1
                    path = manifest.relic_subject_home / "gumi_cron_manifest.json"
                    print(path.read_text(encoding="utf-8"))
                    return 0
                if args.cron_action == "validate":
                    valid, errors = registry.validate_subject(args.subject_id)
                    if valid:
                        print(f"Subject '{args.subject_id}' cron artifacts are valid.")
                        return 0
                    for err in errors:
                        print(err, file=sys.stderr)
                    return 1
            parser.print_help()
            return 1

        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(profile_main())
