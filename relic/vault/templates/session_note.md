# Session Note Template

**Purpose:** Privacy-preserved session summary for vault export/regeneration

**Inputs:** Session metadata and hashes (NO raw content)

**Outputs:** Session summary that can be used to verify session state

## Privacy Notes

- Raw chat content is NEVER included
- Only SHA-256 hashes are stored
- All content must pass privacy gate before export

## Template Fields

```markdown
## Session Summary

- **Session ID:** {{session_id}}
- **Created At:** {{created_at}}
- **Privacy Level:** {{privacy_level}}
- **Content Hash:** {{content_hash}}

## Activity Summary

- **Prompt Count:** {{prompt_count}}
- **Correction Count:** {{correction_count}}
- **Last Activity:** {{last_activity}}

## Audit Trail

- **Trace ID:** {{trace_id}}
- **Export Date:** {{exported_at}}
```

## Verification

This note can be used to verify session state without accessing raw content.
The content_hash allows verification against the DB record.
