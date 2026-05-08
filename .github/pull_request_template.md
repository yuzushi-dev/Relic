## Summary

- 

## Verification

- [ ] `make lint`
- [ ] `pytest -q`
- [ ] `python3 scripts/ci/check_json_jsonl.py`
- [ ] `python3 scripts/ci/check_no_raw_private_data.py`
- [ ] UI changes: `cd ui && npm audit --audit-level=moderate && npm run build:static`

## Privacy Checklist

- [ ] No real subject data, chat exports, credentials, local Hermes profiles, databases, logs, or generated private artifacts are included.
- [ ] New fixtures are synthetic or redacted.
