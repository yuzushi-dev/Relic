# Paperclip Integration — Setup & Architecture

Relic uses [Paperclip](https://github.com/paperclipai/paperclip) (MIT) as the orchestration layer for its verification pipeline. This document explains the architecture, how to bootstrap it from scratch, and what each component does.

---

## What Paperclip does in Relic

Each analysis module in Relic runs a **three-layer pipeline** before applying any finding:

```
Layer 1: Python (deterministic)
    Compute metrics, aggregate evidence, prepare structured data.
    No LLM calls — this layer is always reproducible.

Layer 2: Pro/Contra/Judge structured deliberation  (lib/relic_debate.py)
    Three calls with role-specific system prompts force documentation
    of competing perspectives before the finding advances:
    - Pro role:    argues the finding is significant
    - Contra role: identifies confounds or insufficient evidence
    - Judge role:  synthesizes verdict + confidence from both arguments
    Default: single model (openrouter/free) with role-differentiated prompts.
    Per-role model overrides supported via RELIC_<DOMAIN>_<ROLE>_MODEL env vars.

Layer 3: Gemini reviewer  (gemini_local adapter, Paperclip)
    An independent Gemini agent receives the raw data + a formal rubric.
    It derives its own verdict WITHOUT seeing the analyst's recommendation.
    Convergence  → finding applied automatically
    Divergence   → CONTESTED (escalated to human via Telegram)
```

The reviewer is **blind**: it reads raw metrics and its own `REVIEW_CRITERIA.md`, not the analyst's conclusion. This prevents anchoring and implements a basic inter-rater reliability check.

---

## Four review teams

| Team | Analyst module | Reviewer | Frequency | What it reviews |
|------|---------------|----------|-----------|-----------------|
| **Health** | `relic_health_monitor` | Health Strategist | every 12h | Model confidence, coverage, bootstrap loop risk |
| **Humanness** | `relic_humanness_analyst` | Humanness Reviewer | daily | AI-pattern degradation in relational agent messages |
| **Biofeedback** | `relic_biofeedback_correlation` | Biofeedback Reviewer | daily 04:15 | Spearman correlations between bio signals and personality facets |
| **Inquiry** | `relic_inquiry_team` | Inquiry Reviewer | on synthesis | Behavioral hypothesis verification |

Each team is a pair: one **analyst** (process adapter, runs Python) + one **reviewer** (gemini_local adapter, runs Gemini CLI).

---

## Prerequisites

1. **Node.js 18+** — for Paperclip
2. **Paperclip installed**:
   ```bash
   npm install -g paperclipai
   ```
3. **Gemini CLI authenticated** (used by gemini_local adapter):
   ```bash
   gemini auth login
   ```
4. **Relic installed** (editable):
   ```bash
   pip install -e .
   ```

---

## Quick setup (recommended)

```bash
# Start Paperclip server (keep this terminal open)
npx paperclipai run

# In another terminal:
python3 scripts/setup_paperclip.py
```

The setup script will:
1. Connect to `http://localhost:3100` and verify Paperclip is running
2. Ask which teams to enable (default: all four)
3. Create a Paperclip company named "Relic" (or your choice)
4. Create analyst + reviewer agents for each selected team
5. Print the environment variables to add to `.env`

After running, add the printed variables to your `.env`:

```env
PAPERCLIP_API_URL=http://localhost:3100
PAPERCLIP_COMPANY_ID=<uuid>
PAPERCLIP_BIO_ANALYST_KEY=<token>
PAPERCLIP_BIO_REVIEWER_ID=<uuid>
PAPERCLIP_INQ_ANALYST_KEY=<token>
PAPERCLIP_INQ_REVIEWER_ID=<uuid>
PAPERCLIP_HEALTH_ANALYST_KEY=<token>
PAPERCLIP_HEALTH_REVIEWER_ID=<uuid>
PAPERCLIP_HUMANNESS_ANALYST_KEY=<token>
PAPERCLIP_HUMANNESS_REVIEWER_ID=<uuid>
```

---

## Workspace bootstrap

After creating agents, each reviewer agent needs workspace files to operate correctly. These files define the review rubric and operational protocol.

Paperclip stores workspaces under:
```
~/.paperclip/instances/default/workspaces/<reviewer-agent-uuid>/
```

Each workspace needs:
- `REVIEW_CRITERIA.md` — formal rubric with numeric thresholds and decision matrix
- `RELIC_INSTRUCTIONS.md` — operational protocol (how to approve/reject/escalate)
- Symlinks to live data files in `RELIC_DATA_DIR`

The `setup_paperclip.py` script does **not** currently write workspace files automatically (Paperclip's API does not expose workspace write endpoints). You must populate them manually after setup.

### Manual workspace population

```bash
RELIC_DATA_DIR=~/.relic/<your-subject-id>
WS=~/.paperclip/instances/default/workspaces

# Create required data files if they don't exist
touch "$RELIC_DATA_DIR/health_overrides.json"
touch "$RELIC_DATA_DIR/humanness_overrides.json"
touch "$RELIC_DATA_DIR/biofeedback_findings.json"
touch "$RELIC_DATA_DIR/inquiry_verdicts.json"
touch "$RELIC_DATA_DIR/reviewer_decisions.jsonl"

# For each reviewer agent, symlink the audit trail
# (replace <uuid> with the actual reviewer agent UUID from .env)
ln -sf "$RELIC_DATA_DIR/reviewer_decisions.jsonl" \
    "$WS/<health-reviewer-uuid>/reviewer_decisions.jsonl"
ln -sf "$RELIC_DATA_DIR/reviewer_decisions.jsonl" \
    "$WS/<humanness-reviewer-uuid>/reviewer_decisions.jsonl"
ln -sf "$RELIC_DATA_DIR/reviewer_decisions.jsonl" \
    "$WS/<bio-reviewer-uuid>/reviewer_decisions.jsonl"
ln -sf "$RELIC_DATA_DIR/reviewer_decisions.jsonl" \
    "$WS/<inq-reviewer-uuid>/reviewer_decisions.jsonl"

# Symlink override files so reviewer writes land in the right place
ln -sf "$RELIC_DATA_DIR/health_overrides.json" \
    "$WS/<health-reviewer-uuid>/health_overrides.json"
ln -sf "$RELIC_DATA_DIR/humanness_overrides.json" \
    "$WS/<humanness-reviewer-uuid>/humanness_overrides.json"
ln -sf "$RELIC_DATA_DIR/biofeedback_findings.json" \
    "$WS/<bio-reviewer-uuid>/biofeedback_findings.json"
ln -sf "$RELIC_DATA_DIR/inquiry_verdicts.json" \
    "$WS/<inq-reviewer-uuid>/inquiry_verdicts.json"
```

Then copy the `REVIEW_CRITERIA.md` and `RELIC_INSTRUCTIONS.md` files into each workspace. Template versions are shipped in `docs/workspace-templates/` (see below).

---

## Workspace file reference

### REVIEW_CRITERIA.md

Defines the review rubric for each team. The reviewer reads this file before issuing a verdict. Key sections:

- **Numeric thresholds / Statistical thresholds** — when evidence is sufficient
- **Data sources** — which workspace files to read (and in what order)
- **Verdict options** — the exact set of valid verdicts
- **Output format** — JSON schema the reviewer must write
- **Decision matrix** — APPROVE / REJECT / CONTESTED rules
- **Independent reasoning requirement** — explicit instruction to derive verdict from data, not from the debate

### RELIC_INSTRUCTIONS.md

Operational protocol:

- **APPROVE**: write the output file + send Telegram notification
- **REJECT**: log reason, do not write output file
- **CONTESTED**: send Telegram with three concrete options (A/B/C) for human approval

Telegram notification env vars required:
```env
RELIC_HEALTH_TELEGRAM_CHAT_ID=
RELIC_HEALTH_TELEGRAM_THREAD_ID=
RELIC_HUMANNESS_TELEGRAM_CHAT_ID=
RELIC_HUMANNESS_TELEGRAM_THREAD_ID=
RELIC_CORR_TELEGRAM_CHAT_ID=
RELIC_CORR_TELEGRAM_THREAD_ID=
TELEGRAM_INQUIRY_CHAT_ID=
TELEGRAM_INQUIRY_THREAD_ID=
```

---

## Debate system configuration

The Pro/Contra/Judge debate uses LLMs configured per domain. By default all roles use `openrouter/openrouter/free`. Override per domain:

```env
# Per-role models (fall back to RELIC_INQUIRY_* if domain-specific not set)
RELIC_HEALTH_PRO_MODEL=openrouter/openrouter/free
RELIC_HEALTH_CONTRA_MODEL=openrouter/openrouter/free
RELIC_HEALTH_JUDGE_MODEL=openrouter/openrouter/free

RELIC_HUMANNESS_PRO_MODEL=openrouter/openrouter/free
RELIC_HUMANNESS_CONTRA_MODEL=openrouter/openrouter/free
RELIC_HUMANNESS_JUDGE_MODEL=openrouter/openrouter/free

RELIC_BIO_PRO_MODEL=openrouter/openrouter/free
RELIC_BIO_CONTRA_MODEL=openrouter/openrouter/free
RELIC_BIO_JUDGE_MODEL=openrouter/openrouter/free

# Inquiry uses RELIC_INQUIRY_* as canonical names
RELIC_INQUIRY_PRO_MODEL=openrouter/openrouter/free
RELIC_INQUIRY_CONTRA_MODEL=openrouter/openrouter/free
RELIC_INQUIRY_MODEL=openrouter/openrouter/free
```

Provider routing is determined by model string prefix:
- `openrouter/` → OpenRouter (`OPENROUTER_API_KEY`)
- `nvidia/` → NVIDIA NIM (`NVIDIA_NIM_API_KEY`)
- `claude` → Anthropic (`ANTHROPIC_API_KEY`)
- `gpt` → OpenAI (`OPENAI_API_KEY`)
- anything else → Ollama (local, no key needed)

---

## Audit trail

All reviewer decisions are appended to `reviewer_decisions.jsonl` in `RELIC_DATA_DIR`. Format:

```jsonl
{"ts": "2026-04-25T03:12:00Z", "domain": "health", "decision": "approve", "rationale": "...", "confidence": 0.82}
{"ts": "2026-04-25T04:17:00Z", "domain": "bio", "decision": "contested", "rationale": "...", "hypothesis_id": null}
```

This file is append-only. Never truncate or overwrite it. It is the ground truth of what the automated pipeline decided and why.

---

## Verifying the integration

```bash
# Check Paperclip is running
curl -s http://localhost:3100/api/health | python3 -m json.tool

# Run health analyst manually (requires RELIC_DATA_DIR and PAPERCLIP_* env vars set)
source .env && python3 -m relic.health_monitor

# Check workspace was populated
ls ~/.paperclip/instances/default/workspaces/<health-reviewer-uuid>/

# Check audit trail
tail -f ~/.relic/<subject-id>/reviewer_decisions.jsonl
```

---

## Troubleshooting

**Reviewer does not write override file**: check that the symlink in the workspace points to a writable path in `RELIC_DATA_DIR`. The symlink must resolve to an existing file (even empty `{}`).

**Debate returns empty verdict**: the `openrouter/free` model may time out or refuse the prompt. Check `RELIC_DATA_DIR` logs or set a more capable model for the Judge role.

**Gemini reviewer sends no Telegram**: verify `TELEGRAM_BOT_TOKEN` and the relevant `*_TELEGRAM_CHAT_ID` are set in `.env` and sourced before running the cron.

**Workspace not found warning in logs**: the analyst logs `workspace_not_found` if `PAPERCLIP_<TEAM>_REVIEWER_ID` is set but the workspace directory does not exist under `PAPERCLIP_WORKSPACE_ROOT`. Run `npx paperclipai run` and let the reviewer agent heartbeat once to create the workspace.
