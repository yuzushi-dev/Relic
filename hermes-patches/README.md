# hermes-patches

Local modifications to the upstream [NousResearch hermes-agent](https://github.com/NousResearch/hermes-agent)
that are not part of any official release and must be reapplied after a
`hermes update` overwrites the installed tree.

Relic loads as a hermes plugin and provides most of its behaviour through the
plugin hook surface (`relic/hermes_plugin/...`), which lives in this repo and is
version-controlled normally. The patches here cover the few changes that have to
live in hermes core because no hook seam exists for them.

## Patches

### `gateway-run-py.patch` — base `a91a57fa5` (v0.14.0)

Full local divergence of `gateway/run.py`. Hunks:

- **Status leak gate** (`_status_callback_sync`): suppress `lifecycle` and
  `warn` events from subject chats unless `display.show_auxiliary_warnings_in_chat`
  is set. Stops retry/rate-limit notices (e.g. `⏱️ Rate limited. Waiting…`) from
  leaking into a subject's chat.
- **Capacity-failure suppression** (end of `_run_agent`): on a subject-facing
  rate-limit / transient-infra failure, suppress delivery of the raw technical
  error and drop a `state/pending_reply.json` marker. The relic context layer
  (`relic/hermes_plugin/pending_reply.py` + `hermes_entry`) reads that marker and
  has the model acknowledge the delay in character on the next generation with
  capacity (only when the gap exceeds 60 minutes).
- Pre-existing local toggles: `_load_show_background_review_in_chat`,
  `_load_show_auxiliary_warnings_in_chat`, and gating of
  `background_review_callback`.

## Reapply after an update

```bash
HERMES_AGENT_DIR=~/.hermes/hermes-agent ./apply.sh
```

The script is idempotent (skips already-applied patches) and falls back to
`git apply --3way` when the base has moved. After applying, restart the gateways.

## Regenerate after editing the live tree

```bash
git -C ~/.hermes/hermes-agent diff gateway/run.py > hermes-patches/gateway-run-py.patch
```
