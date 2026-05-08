# Relic Hermes Plugin Bootstrap

**Status:** normative  
**Owner:** hermes-integration-reviewer  
**Document Version:** 1.0.0

## Purpose

This document defines the bootstrap contract for the Relic Hermes plugin, ensuring secure and privacy-preserving integration with Hermes runtime.

## Integration Classification

- **Integration class:** `internal-blueprint-component`
- **Hermes-native:** not applicable (plugin-based)
- **Runtime dependency added:** no
- **Install/verification allowed:** no

## Key Guarantees

The Relic Hermes plugin provides the following guarantees:

1. **Plugin failure produces NO memory injection**
2. **Only ephemeral per-turn context** (no persistent system prompt changes)
3. **SOUL.md, MEMORY.md, USER.md are never mutated**
4. **`/relic why` works on last CAC trace**
5. **`/relic pause` disables all runtime guidance**
6. **Pre-tool-call enforces TOOL_PERMISSION_MATRIX.md**
7. **Roleplay mode cannot trigger L2+ side-effect tools**
8. **All tool permission decisions are auditable with reason_code and policy_version**

## Inputs

### Configuration

```yaml
relic:
  plugin:
    enabled: true
  privacy:
    gateway_enabled: true
  tool_permissions:
    matrix_path: TOOL_PERMISSION_MATRIX.md
```

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `enabled` | bool | Enable/disable plugin |
| `privacy_gateway_enabled` | bool | Enable privacy gateway |
| `policy_version` | string | Policy version for audit trail |
| `fail_safe_enabled` | bool | Enable fail-safe mechanisms |

## Outputs

### Plugin Lifecycle

The plugin implements the standard Hermes lifecycle:

```python
class RelicHermesPlugin:
    def load(self, config: PluginConfig) -> PluginLoadResult: ...
    def unload(self) -> None: ...
    def shutdown(self) -> None: ...
```

### Ephemeral Context

```python
def inject_ephemeral_context(session_id: UUID | None = None) -> dict | None:
    """Returns ephemeral context for current turn.
    
    Never writes to SOUL.md, MEMORY.md, or USER.md.
    Context is only valid for current turn.
    """
```

### Commands

| Command | Description |
|---------|-------------|
| `/relic why` | Show last CAC trace |
| `/relic pause` | Disable runtime guidance |
| `/relic resume` | Re-enable runtime guidance |
| `/relic status` | Show plugin status |

## Acceptance Checks

### Lifecycle Verification

- [ ] Plugin loads successfully with valid config
- [ ] Plugin fails gracefully with invalid config
- [ ] Plugin unload clears cached state
- [ ] Plugin shutdown transitions to SHUTDOWN state

### Memory Isolation

- [ ] Plugin failure produces NO memory injection
- [ ] `inject_ephemeral_context` returns ephemeral data only
- [ ] No SOUL.md, MEMORY.md, or USER.md mutations
- [ ] No persistent system prompt changes

### Permission Enforcement

- [ ] Pre-tool-call checks permissions before execution
- [ ] L2 tools blocked in roleplay mode without approval
- [ ] L3 tools always blocked
- [ ] All decisions have reason_code and policy_version
- [ ] Audit log has no raw prompts or private text

### Command Verification

- [ ] `/relic why` returns last CAC trace
- [ ] `/relic pause` disables guidance
- [ ] `/relic resume` re-enables guidance
- [ ] Commands are ephemeral (no persistent effects)

### Privacy Checks

- [ ] No raw prompts in audit logs
- [ ] No raw private text in traces
- [ ] MEMORY.md, USER.md never accessed by plugin
- [ ] SOUL.md never accessed by plugin

## Block Conditions

The following conditions will block plugin integration:

- Plugin failure still injects guidance
- `/relic pause` can be bypassed
- Plugin can call lab promotion
- Plugin executes a side-effect tool without permission decision
- Roleplay frame can trigger filesystem, network, email, calendar, or shell side effect
- Tool permission trace stores raw prompt or raw private text

## Tool Permission Matrix

### Category: read-only

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `memory.read` | Read from memory store | `context:read` |
| `context.read` | Read prompt context | `context:read` |
| `provider.list` | List available providers | `context:read` |

### Category: write-once

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `memory.append` | Append to memory | `context:write`, `audit:write` |
| `audit.log` | Write audit log entry | `audit:write` |

### Category: side-effect L1

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `memory.update` | Update existing memory | `memory:modify` |

### Category: side-effect L2 (blocked in roleplay)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `memory.delete` | Delete memory | `privacy:gate` |
| `provider.call` | Call external provider | `privacy:gate` |
| `filesystem.write` | Write to filesystem | `privacy:gate` |
| `network.http` | HTTP requests | `privacy:gate` |
| `email.send` | Send emails | `privacy:gate` |
| `calendar.event` | Create calendar events | `privacy:gate` |

### Category: side-effect L3 (always blocked)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `tool.execute` | Execute arbitrary tool | `security:override` |
| `shell.execute` | Execute shell commands | `security:override` |
| `lab.promote` | Lab promotion | `security:override` |

## Bootstrap Script

The bootstrap script `scripts/hermes/check_relic_plugin_bootstrap.sh` provides:

- `--dry-run` mode for verification without live credentials
- Strict mode (`set -euo pipefail`)
- No secret printing
- Graceful handling of missing configuration

## Required Reviewers

- **hermes-integration-reviewer:** Plugin lifecycle and Hermes integration
- **security-privacy-reviewer:** Permission enforcement and privacy guarantees
- **architecture-reviewer:** System design consistency
