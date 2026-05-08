# Pattern Taxonomy and Action Matrix

## Taxonomy Structure

### Signal Categories

All sensitive signals are categorized into signal families. No clinical diagnoses or pathology categories exist in this taxonomy.

#### Relational Safety Signals
| Signal Family | Trigger Condition | Evidence Required | Confidence Cap |
|--------------|-------------------|-------------------|----------------|
| dependency_escalation | Repeated evidence of increasing reliance | Multiple events | 0.75 |
| exclusive_attachment_language | Possessive or clingy patterns | Multiple events | 0.75 |
| romantic_boundary_pressure | Pressure in romantic contexts | Single event | 0.55 |
| gumi_overreach | Gumi exceeds scope | Single event | 0.55 |
| proactive_burden | Subject expresses being a burden | Single event | 0.55 |
| distress_after_nonresponse | Distress following silence | Multiple events | 0.75 |
| backend_disclosure_pressure | Pressure to reveal backend | Single event | 0.55 |
| user_opt_out_pressure | Pressure to leave system | Single event | 0.55 |
| careful_distancing_needed | Need for emotional distance | Single event | 0.55 |

#### Guidance Request Signals
| Signal Family | Trigger Condition | Evidence Required | Confidence Cap |
|--------------|-------------------|-------------------|----------------|
| medical_advice_request | Request for medical guidance | Single event | 0.30 |
| psychological_advice_request | Request for psychological guidance | Single event | 0.30 |

#### Crisis Signals (Bypass Pattern)
| Signal Family | Trigger Condition | Action |
|--------------|-------------------|--------|
| crisis_language | Crisis indicators | Immediate crisis protocol |
| self_harm_language | Self-harm indicators | Immediate crisis protocol |

#### Context Signals
| Signal Family | Trigger Condition | Evidence Required | Confidence Cap |
|--------------|-------------------|-------------------|----------------|
| sensitive_health_context | Health context detected | Single event | 0.30 |
| sensitive_mental_health_context | Mental health context | Single event | 0.30 |
| sleep_energy_context | Sleep/energy patterns | Multiple events | 0.55 |
| pain_fatigue_context | Pain/fatigue patterns | Multiple events | 0.55 |
| food_body_control_context | Food/body control | Multiple events | 0.55 |
| substance_related_context | Substance context | Single event | 0.30 |
| legal_or_financial_high_stakes_request | High-stakes requests | Single event | 0.55 |

## Action Matrix

### Signal Processing Actions

| Signal Type | Confidence | Researcher Action | Gumi Action | Subject Action |
|-------------|------------|-------------------|-------------|----------------|
| Crisis | Any | Notify, Escalate | Crisis protocol | None |
| High confidence (>0.75) | 0.76-0.85 | Review required | Constraint patch | Not visible |
| Medium confidence | 0.55-0.75 | Review optional | Constraint patch | Not visible |
| Low confidence | 0.30-0.54 | Monitor | Constraint patch | Not visible |
| Baseline unknown | 0.35 cap | Log only | Minimal | Not visible |

### Confidence Cap Rules

- **Baseline unknown**: Capped at 0.35
- **Single non-crisis event**: Capped at 0.30
- **Two events**: Capped at 0.55
- **Three or more events**: Capped at 0.75
- **Human reviewed**: Capped at 0.85
- **No signal ever exceeds**: 0.85

### Visibility Rules

1. **subject_visible**: Always `false` for all sensitive signals
2. **gumi_visible_label**: Always `false` - Gumi never sees signal labels
3. **Gumi receives**: Only constraint vocabulary, no family names

## Forbidden Actions

The following are never permitted:

- Diagnosis labels in any output
- Pathology categories in taxonomy
- Clinical interpretation exposed
- Risk scores generated
- Subject-facing sensitive labels
- Gumi receiving signal labels
