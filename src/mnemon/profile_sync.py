"""Cron entrypoint: relic:profile-sync

Invoked as: python -m relic.profile_sync
Schedule:   30 3 * * *   (daily at 03:30, after synthesize)

Syncs the current trait model to subject_profile.json and regenerates
the human-readable PORTRAIT.md that is injected into agent sessions
by the relic-bootstrap hook.
"""
from mnemon.relic_profile_bridge import main

if __name__ == "__main__":
    main()
