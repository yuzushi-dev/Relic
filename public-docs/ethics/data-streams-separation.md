# Data Stream Separation

One of the core architectural invariants in Relic is that different kinds of interaction data are kept separate and cannot be collapsed into a single evidence pool.

## The five streams

| Stream | Description | Can update subject model? |
|---|---|---|
| Passive interaction | What the subject says and does during conversation | Yes, after ingestion and review |
| Active elicitation | Structured questions Gumi asks to gather specific information | Yes, with source labeled |
| Gumi diegetic events | Events in Gumi's fictional life: her routines, experiences, creative acts | No |
| Expressive media | Images, audio, generated content sent by Gumi | No (only subject responses may be eligible) |
| User responses to Gumi | Subject replies to diegetic or expressive content | Yes, if the response is eligible for ingestion |

## Why this matters

The most common failure mode to avoid is using Gumi's own outputs as evidence about the subject. If Gumi sends a melancholy audio message and the subject replies "that was beautiful, I felt that too," the relevant signal is in the subject's response, not in Gumi's act of sending the message.

Collapsing these streams would produce an evidence pool contaminated by the system's own outputs. A subject who engages warmly with Gumi's creative acts would appear more "expressive" or "open" not because of anything true about them, but because Gumi generates content they respond to. This creates a feedback loop where the model reinforces its own assumptions.

The ontological class field on every event (`relic/schemas.py`) enforces this distinction at the data model level. Events with class `gumi_diegetic_event` or `expressive_media` do not update the subject model by themselves. Only events with an eligible class — primarily `empirical_user_interaction`, `active_elicitation`, and `user_response_to_gumi` — can be used as evidence.

## Evidence eligibility

Not every user response is eligible for ingestion. A response to a diegetic event is eligible only if:

1. The response is clearly about the subject's own experience, not a reaction to the fictional content.
2. The response has not been elicited by manipulative or leading framing.
3. The ingestion passes the privacy and correction gates.

The boundary is enforced in tests: `tests/ui/test_user_response_can_be_eligible_evidence.py` and `tests/ui/test_gumi_generated_event_not_user_evidence.py`.

## Researcher and system streams

A separate separation applies to researcher-generated data (corrections, feedback events, eval annotations) and system-generated data (inferred fields, confidence updates). These are tracked with their source, so a profile can always distinguish between what the subject said, what the researcher decided, and what the system inferred.

Inferred fields have explicit confidence caps and are not directly injected into the runtime context. See `relic/profile/inferred_fields.py` and the tests under `tests/profile/test_inferred_fields_*.py`.
