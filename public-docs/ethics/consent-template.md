# Consent Template

A starting point for the participant consent document. **This is not legal advice.** Adapt it to your institutional review board, jurisdiction, and study design. Have it reviewed by your IRB/ethics committee and a data-protection officer before use.

The template covers the consent categories Relic understands at the data-model level (`relic/control/consent.py`). Each category maps to a specific runtime behavior.

---

## Sample participant consent form

> ### Participation in [Study Name]
>
> You are being invited to take part in a research study that uses a conversational AI system called Gumi. Before you decide, please read this document carefully and ask questions if anything is unclear.
>
> #### What the study does
>
> The study observes a series of conversations between you and Gumi over [N weeks/months]. Gumi is an AI agent that remembers what you have told her in the past. The study examines how that memory affects the conversation over time and how you experience it. There is no clinical or therapeutic intervention. Gumi does not diagnose, treat, or replace any form of professional support.
>
> #### What we will collect
>
> - The text of your conversations with Gumi.
> - Structured estimates of behavioral patterns we derive from those conversations.
> - Memory markers you confirm with Gumi (things you ask her to remember).
> - System metadata: timestamps, session lengths, delivery decisions.
>
> We do **not** collect anything outside the conversation. Gumi does not access your other apps, contacts, or files.
>
> #### What we will not do
>
> - We will not infer or record any clinical diagnosis about you.
> - We will not share your raw conversations with any third party.
> - We will not use generated media (images, voice) as evidence about you unless you respond to them and the response is conversational data.
> - We will not let Gumi's own narrative events (her life, her fictional experiences) count as observations about you.
>
> #### Specific permissions
>
> Please tick the boxes that apply. You can change any of these at any time by contacting the researcher.
>
> - [ ] **Conversation storage.** I agree that my conversations with Gumi may be stored locally for the duration of the study and processed for research purposes.
> - [ ] **Memory storage.** I agree that Gumi may remember what I tell her across sessions, with the limits described above. (`memory_storage`)
> - [ ] **Delivery.** I agree to receive messages from Gumi through the channel I have specified (e.g. Telegram). (`delivery`)
> - [ ] **Proactivity.** I agree that Gumi may initiate contact (send the first message in a session) within the quiet-hours and frequency limits agreed at enrolment. (`proactivity`)
> - [ ] **Generated media.** I agree that Gumi may send generated images, voice notes, or short music clips as part of the conversation. (`media_generation`)
> - [ ] **Researcher review.** I understand that a researcher can read the conversations, the system's model of me, and the system's decisions, for the purposes of the study and the system's safety governance.
>
> #### Your rights
>
> At any time you can:
>
> - **Pause** Gumi temporarily. She will stop sending proactive messages and stop personalising her responses. You can resume when you want.
> - **Correct** anything the system has inferred about you. Corrections are authoritative; the system cannot reinstate the original value.
> - **Export** all your data in a portable format.
> - **Delete** all your data permanently. After deletion, the system retains an anonymised audit record only, as required by [applicable law].
>
> You can exercise any of these rights by contacting [researcher name, email, response time].
>
> #### Risks and limits
>
> - Gumi is an AI. She is presented as a relational character, but she is not a person and not a friend. She does not have feelings, does not need you, and is not affected by what you tell her.
> - Gumi is not a clinical tool. She does not provide medical, psychological, or crisis support. If you are in crisis, please contact [local crisis line] or a qualified professional.
> - Memory is imperfect. Gumi may misremember, take initiative at the wrong moment, or strike the wrong tone. You can correct any of this.
> - The system may flag specific patterns of conversation for researcher review. Those flags are governance signals and are never used as clinical assessments.
>
> #### Storage and security
>
> Your data is stored on a local machine controlled by the research team. It is not uploaded to any cloud service. The researcher's responsibilities for storage are described in [data-management plan reference].
>
> #### Withdrawal
>
> You can withdraw from the study at any time without giving a reason and without any consequence. Upon withdrawal, your data will be exported and deleted within [N] days unless you ask otherwise.
>
> #### Contact
>
> - Researcher: [name, role, email]
> - Data Protection Officer: [name, email]
> - Ethics committee: [name, reference number]
>
> #### Signature
>
> I have read and understood this document. I have had the opportunity to ask questions. I freely agree to take part in the study under the conditions stated above.
>
> Participant name: ______________________   Signature: ______________________   Date: __________
>
> Researcher name: ______________________   Signature: ______________________   Date: __________

---

## Mapping the form to Relic consent types

The ticks on the form correspond to entries in `ConsentManager` (`relic/control/consent.py`):

| Form box | Consent type |
|---|---|
| Memory storage | `ConsentType.MEMORY_STORAGE` |
| Delivery | `ConsentType.DELIVERY` |
| Proactivity | `ConsentType.PROACTIVITY` |
| Generated media | `ConsentType.MEDIA_GENERATION` |
| Researcher review | (implicit; required for participation) |

Record the ticks at the **Consent** step of `relic subject create`. The bootstrap TUI writes the consent record into `relic.db` and the runtime gates every action against it.

## Operational notes

- Quiet hours and frequency caps are set per subject during bootstrap (`relic-profile hermes configure-telegram --quiet-hours ... --maximum-contact-frequency ...`). Negotiate them with the participant before enrolment and write the agreed values on the form.
- "Researcher review" is not optional in the current architecture: the workbench reads system state by design. If a participant declines researcher review, they should not be enrolled.
- A revoked consent takes effect immediately at the runtime gate. See [Consent revocation](../guides/export-and-deletion.md#consent-revocation).

## Related reading

- [Ethics](index.md) — the core ethical commitments the system enforces.
- [Consent and Control](consent-and-control.md) — how consent flows through the system.
- [Behavioral Boundaries](boundaries.md) — what Gumi will and will not do.
- [Export and Deletion](../guides/export-and-deletion.md) — the operational side of participant rights.
