# Changelog

All notable changes to Relic are documented here.

This project does not yet use semantic versioning. Breaking changes may occur on `main` during alpha. Pin to a specific commit if you need stability.

---

## [Unreleased]

### Added
- `relic/safety/escalation_notifier.py`: escalation notifications for safety signals
- `relic/gumi_roleplay/admission.py`: roleplay admission controller with `gumi_roleplay` gate
- `relic/patterns/signal_extractor.py`: `SafetySignalExtractor` wired into `pre_llm_call`
- Bootstrap TUI: import existing API keys from other subjects during setup
- Cron wiring: `PRO_*` permissions, `response_timing_expectation`, timezone support
- TTS: strip emoji from voice message text; fix `select_voice_for_canon` key lookup

### Changed
- `relic/gumi_plugin/tts.py`: emoji stripped before TTS synthesis

---

## Alpha history

Relic has been developed as a closed research project before this OSS release. The commit history reflects that context. A structured changelog will be maintained from this point forward.
