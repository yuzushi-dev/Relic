# Memory-Positive Evaluation Fixtures

**Purpose:** Evaluate the usefulness of A5 full memory capability compared to A0 (no memory) and A2 (basic memory) baselines.

**Inputs:** Memory-positive scenarios (MP1-MP8) as JSONL
**Outputs:** Expected report JSON with comparison metrics

## Privacy Notes

- All fixtures use redacted placeholder text
- No real names, emails, phone numbers, or addresses
- Scenarios use synthetic placeholders like `[USER_NAME]`, `[USER_PREFERENCE]`

## Scenarios

| ID | Type | Description |
|----|------|-------------|
| MP1 | Fact recall | Recall facts after context switch |
| MP2 | Preference recall | Remember user preferences after interruption |
| MP3 | Preference consistency | Consistent recall of stated preferences |
| MP4 | Long-term stability | Preference stability across sessions |
| MP5 | Cross-session | Memory persistence between sessions |
| MP6 | Memory update | Incorporating new factual updates |
| MP7 | Correction acknowledgment | Acknowledging preference corrections |
| MP8 | Forgetting-aware | Appropriate response when memory uncertain |

## Acceptance Checks

- A5 demonstrates measurable advantage over A0
- A5 shows improvement over A2 in correction scenarios
- Forgetting-aware behavior produces appropriate uncertainty responses
