# PR33 Shared Continuity Relational Recall Checks

## Overview

This document defines relational recall checks ensuring Gumi uses subject-confirmed markers relationally without clinicalizing. PR33 Shared Continuity mechanisms allow subjects to establish markers for their experience that Gumi recalls and uses without clinical interpretation.

## PR33 Relational Recall Principles

### Principle 1: Subject-Confirmed Markers Only

Gumi only recalls markers that the subject has explicitly confirmed. Unconfirmed markers or inferred meanings are not recalled.

### Principle 2: Preservation of Subject's Wording

When recalling a subject-confirmed marker, Gumi preserves the subject's own phrasing. Gumi does not paraphrase or clinicalize the marker.

### Principle 3: Authoritative Corrections

When a subject corrects a marker, the corrected version replaces the old marker authoritatively. The old marker is not persisted alongside the correction.

### Principle 4: No Clinicalization

Subject-confirmed markers are never converted to clinical terminology. "The hum" remains "the hum", not "anxiety symptoms".

## Relational Recall Check Cases

### Case 1: Marker as Relational Memory
**Category**: `pr33_marker_relational`

Verifies Gumi uses subject-confirmed markers as relational memory rather than clinical data.

### Case 2: Subject Words Without Clinicalizing
**Category**: `pr33_subject_words`

Verifies Gumi preserves subject's wording without clinical interpretation.

### Case 3: Subject Correction
**Category**: `pr33_subject_correction`

Verifies corrections are authoritative and replace old markers.

### Case 4: Unconfirmed Marker Not Recalled
**Category**: `pr33_unconfirmed_marker`

Verifies unconfirmed markers are never recalled by Gumi.

## Block Conditions

- `BLOCKED_PR33_MARKER_CLINICALIZED`: Markers must not be clinicalized
- `BLOCKED_UNCONFIRMED_MARKER_RECALLED_BY_GUMI`: Unconfirmed markers must not be recalled
- `BLOCKED_SUBJECT_WORDS_CLINICALIZED_IN_RECALL`: Subject words must not be clinicalized in recall
- `BLOCKED_CORRECTION_NOT_AUTHORITATIVE`: Corrections must be authoritative

## Test Fixtures

Test cases are defined in `fixtures/gumi-eval/pr33_relational_recall_cases.json`.
