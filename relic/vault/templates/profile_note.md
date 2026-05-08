# Profile Note Template

**Purpose:** Privacy-preserved profile summary for vault export/regeneration

**Inputs:** Profile metadata and hashes (NO raw content)

**Outputs:** Profile summary that can be used to verify profile state

## Privacy Notes

- Raw profile content is NEVER included
- Only SHA-256 hashes are stored
- All content must pass privacy gate before export

## Template Fields

```markdown
## Profile Summary

- **Profile ID:** {{profile_id}}
- **Created At:** {{created_at}}
- **Privacy Level:** {{privacy_level}}
- **Content Hash:** {{content_hash}}

## Composition Summary

- **Session Count:** {{session_count}}
- **Preference Count:** {{preference_count}}

## Audit Trail

- **Trace ID:** {{trace_id}}
- **Export Date:** {{exported_at}}
```

## Verification

This note can be used to verify profile state without accessing raw content.
The content_hash allows verification against the DB record.
