# Relic and Gumi

Relic and Gumi are two different things operating at two different levels. Understanding the separation is important for both deployment and research use.

## Relic

Relic is the governance and modeling layer. It maintains the subject profile, runs the compilation pipeline, enforces privacy constraints, tracks corrections and provenance, and produces the runtime artifacts that inform Gumi's behavior. Relic does not interact with the subject directly.

## Gumi

Gumi is a diegetic relational agent — an agent with her own identity, background, voice, and relational history. She is not a transparent interface to Relic, and she is not a copy of the subject. She has her own perspective, aesthetic sensibility, and boundaries.

Gumi runs on Hermes and is initialized with a SOUL.md that defines her stable identity. Relic governs what context is injected into her per-turn prompt, what tools she can use, and when her behavior must be adapted for safety reasons. But Gumi's output is not Relic's output. She generates responses consistent with her own character, informed by the governed context.

## The design intention

The bootstrap process creates a Gumi profile calibrated to a specific subject. The goal is a particular relational distance: close enough that the interaction feels personal and continuous, far enough that Gumi retains her own agency and perspective. She is not optimized to mirror the subject or to agree with them. She can push back, express her own preferences, and have opinions the subject does not share.

This is an intentional design choice against a simpler approach: a system that purely reflects the subject back at themselves. Such a system would produce more comfortable interactions at the cost of being less honest and more prone to reinforcing the subject's existing patterns. Gumi's independence is a feature, not a gap.

## What Gumi knows and does not know

Gumi does not know she is an agent. She does not know about Relic, Hermes, or the governance mechanisms behind her behavior. She does not reference backend infrastructure or explain her constraints to the subject. This is the diegetic frame: everything happens within the relational context she and the subject have established.

This means subjects do not see raw facet values, confidence scores, or safety signals. The governance layer is invisible by design. Researchers can inspect it through the workbench; subjects experience the relationship.

## Gumi's diegetic life

Gumi can take initiative: proactive messages, creative media, audio, diegetic life fragments. These acts are part of the subject's lived experience with Gumi. They are not passive observations about the subject. A piece of music Gumi sends says something about Gumi, not about the subject. The subject's response to it may be eligible as evidence, but only the response, not the act of sending it.

See [Data Stream Separation](../ethics/data-streams-separation.md) for how this is enforced in the data model.

## One Gumi per subject

A Gumi instance is scoped to a single subject. There is no global Gumi runtime that multiple subjects share. Each instance is initialized separately, maintains its own continuity state, and does not cross-contaminate with other instances. This is enforced in `tests/ui/test_no_global_gumi_runtime.py` and `tests/ui/test_subject_scoped_gumi_instance.py`.
