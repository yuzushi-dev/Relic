# Multi-Researcher Setup

How to run a study with more than one researcher. Covers identity, role permissions, study scoping, and the limits of the current implementation.

## Honest status

The data model has roles, permissions, and `researcher_id` everywhere. The **operational** layer (auth, login, identity verification) is not in the OSS distribution. In practice that means:

- The system records which `researcher_id` performed which action — for audit.
- Role-based permissions are enforced at the API layer.
- There is **no built-in login**, password manager, or session UI. Researchers identify themselves with the IDs you assign at deployment time.

This is sufficient for small teams (2–10 researchers) running co-located studies under shared infrastructure. For larger or geographically distributed teams, put Relic behind your institution's identity provider; see [Putting Relic behind your IdP](#putting-relic-behind-your-idp) below.

## Researcher identifiers

A `researcher_id` is a free string. Convention: stable institutional handles (e.g. `dveri`, `m.rossi`). Used in:

- `recorded_by_researcher_id` in every consent record (`relic/profile/_bootstrap_steps/consent.py`).
- `researcher_id` in baseline artefacts and edit logs.
- `accessor` field in every chronicle access event (`chronicle query --accessor ...`).
- Workbench audit trail (every UI action).

Pick a convention before enrolling subjects. Changing IDs later does not retroactively rewrite audit records.

## Role matrix

Defined in `relic/ui/permissions.py`:

| Role | `READ_QUEUE` | `READ_ARTIFACT` | `READ_STUDY_OVERVIEW` | `EMIT_FEEDBACK` | `REQUEST_RECOMPILE` | `REPLAY_TRACE` | `EXPORT_BUNDLE` |
|---|---|---|---|---|---|---|---|
| `researcher` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `subject` | — | ✅ | — | ✅ | — | — | — |
| `viewer` | ✅ | ✅ | — | — | — | — | — |

Notes:

- `EXPORT_BUNDLE` is not granted to any default role; export is a privileged operation, gate it through your operational layer.
- The `subject` role is the one a participant uses when self-correcting from a subject-facing interface (not in the OSS workbench by default).
- The `viewer` role is the read-only role you give to people who should see the queue but not act on it (auditors, advisors).

To create a custom matrix:

```python
from relic.ui.permissions import PermissionMatrix, Permission

m = PermissionMatrix.default()
m.grants["external_auditor"] = {Permission.READ_ARTIFACT, Permission.READ_STUDY_OVERVIEW}
```

Persist and load the matrix via your operational layer (config file, IdP claim, etc.). The OSS distribution ships only the in-memory `default()` matrix.

## Study scoping

Subjects belong to an `experiment_id` set at bootstrap (`relic subject create --experiment-id ...`). The workbench filters subjects by study using `relic/ui/permissions.py` plus the registry's per-subject `experiment_id`.

To enforce that a researcher only sees a specific study:

1. Tag every subject in that study with the same `experiment_id`.
2. Wire your operational layer to map `researcher_id` → allowed `experiment_id`s.
3. Filter at API entry. The workbench respects the filter; the CLI does not (it trusts the operator).

For a single team running a single study, scoping is moot — everyone sees everything within the local DB.

## Day-to-day with multiple researchers

Recommended workflow:

```bash
# Each researcher sets RELIC_RESEARCHER_ID in their shell profile.
export RELIC_RESEARCHER_ID="dveri"

# Bootstrap, edit, and CLI commands accept this ID via env or prompt.
relic subject create --subject-id subj_demo_01
# Wizard prompts for `researcher_id`; defaults to RELIC_RESEARCHER_ID if set.

# Chronicle automatically records the accessor.
chronicle query --subject subj_demo_01 --accessor "$RELIC_RESEARCHER_ID"
```

When two researchers act on the same subject, chronicle preserves the full trail. Conflicts (e.g. two contradicting corrections) are flagged in the workbench's review queue, not silently merged.

## Subject-side identity

For the subject, identity is the delivery channel (Telegram user ID). The system does not store the subject's real name unless you collect it during bootstrap's self-report step. Default convention: store a research handle, not the legal name.

## Audit per researcher

```bash
chronicle query --accessor dveri --limit 200
chronicle stats --since 2026-05-01T00:00:00Z          # per-day activity
```

Audit events include the action, target, and outcome. Use `chronicle query --type access` to see every read; use `chronicle query --type correction_applied` to see every write.

## Putting Relic behind your IdP

Out of scope for the OSS distribution. The recommended pattern:

1. Run `relic ui` behind a reverse proxy (nginx, Caddy, Traefik) that handles OIDC/SAML.
2. Inject the IdP-validated user identifier as an HTTP header.
3. Read the header at API entry and pass it to `PermissionMatrix.can(role, perm)`.

The IdP is responsible for authentication; the permission matrix is responsible for authorisation. Do not mix the two layers.

## What is not enforced

- The `RELIC_RESEARCHER_ID` env var is **self-asserted** unless you wrap it in an IdP. A researcher can claim to be someone else.
- There is no password storage, no session, no MFA in OSS.
- The workbench listens on `localhost:8080` by default. Exposing it requires your own reverse proxy with auth.
- CLI commands trust the operator. There is no per-command authorisation check.

Plan accordingly: Relic is a research tool with audit, not a hardened multi-tenant platform.
