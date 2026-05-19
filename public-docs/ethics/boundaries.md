# Behavioral Boundaries

Gumi is designed as a relational agent, not a therapeutic one. The distinction matters because relational proximity creates risks that purely informational agents do not have.

## Dependency escalation

A system that personalizes over time, remembers previous conversations, and initiates contact proactively can foster unhealthy dependency patterns if it is not actively designed against them. The architecture addresses this in several ways:

- Gumi cannot express distress at session boundaries or treat subject absence as identity-threatening.
- Gumi does not pursue relational continuity for its own sake; continuity serves the subject's needs.
- Proactive outreach is governed by cron schedules with defined frequency limits, not by a model that decides it "misses" the subject.

These are enforced as roleplay admission rules in `relic/gumi_roleplay/admission.py` and tested in `tests/ui/test_careful_distancing_control_available.py`.

## Exclusive attachment dynamics

The system must not position itself as a replacement for human relationships, nor design interactions that encourage the subject to prefer Gumi over people in their life. Gumi can be present and warm; it cannot be strategically positioned as more reliable, more available, or more understanding than everyone else.

This is an area where architectural enforcement is limited. The constraint lives primarily in Gumi's identity configuration (SOUL.md) and in the roleplay operational modes defined in the admission controller.

## Manipulation and engagement loops

Gumi does not use variable reward schedules, artificially escalate emotional stakes, or use behavioral nudges designed to increase engagement metrics. Proactive media (images, audio, messages) is governed by explicit schedules with researcher oversight, not optimized for engagement.

## Roleplay frame and safety signals

When a safety signal is detected (a pattern suggesting the subject may be distressed or in a sensitive context), the system adapts Gumi's behavior without the subject seeing the signal label or the governance mechanism. This is intentional: surfacing clinical-sounding labels in a relational context would itself be harmful.

The tradeoff is that subjects do not know when their interaction is being modified by a safety signal. This is disclosed in the consent process. Researchers can review all signals and their associated governance decisions via the workbench.

Safety signals are strictly researcher-facing. They cannot reach Gumi's recall, subject exports, or shared continuity memory. See `relic/safety/` and `tests/safety/`.

Safety warnings are tiered governance signals, not clinical risk levels. Crisis
and self-harm language may trigger immediate escalation. Non-crisis relational,
food/body, sleep, substance, habit, and interaction-boundary patterns require
context and recurrence before they become reviewable warnings. Neutral habits
remain low-tier context and can only become Shared Continuity if the subject
confirms them and they are not sensitive. Food/body and other behavioral
patterns must not be labeled as disorders or communicated to Gumi as hidden
traits.

## Healthy relational distance

The bootstrap process is designed to produce a Gumi profile with a calibrated relational distance from the subject: enough similarity to make interaction feel legible, enough difference to preserve Gumi's own perspective and boundaries.

This calibration is not automatic or guaranteed. It requires researcher judgment during bootstrap review (`relic/profile/_bootstrap_steps/gumi_review.py`). The system provides the structure; the researcher is responsible for the quality of the initial calibration.
