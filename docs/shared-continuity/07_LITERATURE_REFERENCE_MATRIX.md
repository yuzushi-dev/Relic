# Literature Reference Matrix

## Hermes plugin architecture

Source:

```text
Hermes Agent docs - Plugins
```

Relevant point:

```text
Hermes plugins can add custom tools, hooks, commands, injected messages, and bundled skills without modifying Hermes core.
```

Use in PR33:

```text
Shared Continuity Memory is implemented as a general plugin with tools, hooks, and a bundled skill.
```

## Hermes memory/provider boundary

Source:

```text
Hermes Agent docs - Features overview / memory providers
```

Relevant point:

```text
Hermes has bounded native memory and pluggable external memory providers such as Hindsight. Memory providers are broad personalization/recall mechanisms.
```

Use in PR33:

```text
Shared Continuity Memory is not a general memory provider. It is a Relic-governed application memory with consent, correction, TTL, recall limits, and subject scope.
```

## Electronic self-monitoring in bipolar disorder

Source:

```text
Faurholt-Jepsen et al. (2016).
Electronic self-monitoring of mood using IT platforms in adult patients with bipolar disorder:
A systematic review of the validity and evidence.
BMC Psychiatry.
```

Relevant point:

```text
Electronic mood self-monitoring showed stronger validity against depression ratings than mania ratings. Evidence was limited and more rigorous research was needed.
```

Use in PR33:

```text
Do not infer episodes. Preserve descriptive, user-confirmed continuity markers only.
```

## JITAI

Source:

```text
Nahum-Shani et al. (2018).
Just-In-Time Adaptive Interventions in Mobile Health:
Key Components and Design Principles.
Annals of Behavioral Medicine.
```

Relevant point:

```text
Decision points, tailoring variables, intervention options, and decision rules are key components.
```

Use in PR33:

```text
Follow-up cron is a decision point. Due markers, burden, quiet hours, pause state, and recall limits are tailoring variables. NO_REPLY is a valid option.
```

## AI companion risks

Sources:

```text
Nature Machine Intelligence Editorial (2025).
Emotional risks of AI companions demand attention.

De Freitas & Cohen (2025).
Unregulated emotional risks of AI wellness apps.
Nature Machine Intelligence.
```

Relevant point:

```text
AI companions can foster emotional dependence and ambiguous or dysfunctional attachment in vulnerable users.
```

Use in PR33:

```text
Recall limits, careful non-insistence, pause/forget, and burden-aware follow-up are mandatory.
```

## Design conclusion

PR33 uses literature to justify:

```text
descriptive self-continuity
consent
correction
non-diagnostic limits
low-burden follow-up
subject wording
human oversight
```

PR33 does not claim:

```text
clinical efficacy
episode detection
relapse prediction
therapy
diagnosis
```
