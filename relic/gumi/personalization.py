"""Subject-to-Gumi personalization mapper.

Maps scored item-battery data to domain constraints using complementarity theory
(Wiggins 1979 interpersonal circumplex; Aron & Aron 1996 self-expansion;
Fraley 2011 ECR-RS; Gosling 2003 TIPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainConstraint:
    """Sampling constraint for one Gumi background domain."""
    preferred: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    weight: float = 1.0  # 0.0 = ignore, 1.0 = strongly enforce


@dataclass
class PersonalizationConstraints:
    """Per-domain constraints derived from a subject's item-battery scores."""
    subject_id: str
    tipi: dict[str, float]
    ecrrs: dict[str, float]
    project: dict[str, float]
    sweet_spot_target: float

    identity: DomainConstraint = field(default_factory=DomainConstraint)
    embodiment: DomainConstraint = field(default_factory=DomainConstraint)
    place: DomainConstraint = field(default_factory=DomainConstraint)
    life_role: DomainConstraint = field(default_factory=DomainConstraint)
    routine: DomainConstraint = field(default_factory=DomainConstraint)
    passions: DomainConstraint = field(default_factory=DomainConstraint)
    social_world: DomainConstraint = field(default_factory=DomainConstraint)
    relationship_stance: DomainConstraint = field(default_factory=DomainConstraint)
    boundaries: DomainConstraint = field(default_factory=DomainConstraint)

    def for_domain(self, domain: str) -> DomainConstraint:
        return getattr(self, domain, DomainConstraint())


class SubjectPersonalizationMapper:
    """Derive Gumi domain constraints from a subject's scored item battery.

    All mapping rules follow two principles:
    1. Complement vulnerability: where subject is weak/anxious, Gumi is stable.
    2. Allow similarity: shared interests/values aid connection (Aron 1996),
       but occupation, location, family must differ (anti-clone rule).
    """

    def map(
        self,
        item_battery: dict[str, Any],
        subject_baseline: dict[str, Any] | None = None,
    ) -> PersonalizationConstraints:
        """Build PersonalizationConstraints from scored item battery.

        Args:
            item_battery: output of collect_item_battery(), contains 'scores' and 'responses'.
            subject_baseline: optional baseline_user_profile dict for anti-clone field exclusion.
        """
        scores = item_battery.get("scores", {})
        tipi: dict[str, float] = scores.get("tipi", {})
        ecrrs: dict[str, float] = scores.get("ecrrs", {})
        project: dict[str, float] = scores.get("project_calibration", {})
        subject_id = (subject_baseline or {}).get("subject_id", "unknown")

        constraints = PersonalizationConstraints(
            subject_id=subject_id,
            tipi=tipi,
            ecrrs=ecrrs,
            project=project,
            sweet_spot_target=self._compute_sweet_spot_target(tipi, ecrrs, project),
        )

        self._map_relationship_stance(constraints, tipi, ecrrs, project)
        self._map_boundaries(constraints, tipi, project)
        self._map_passions(constraints, tipi, project)
        self._map_social_world(constraints, project)
        self._map_routine(constraints, project)
        self._map_identity(constraints, subject_baseline or {})
        self._map_place(constraints, subject_baseline or {})
        self._map_life_role(constraints, subject_baseline or {})

        return constraints

    # ------------------------------------------------------------------ #
    # Domain mappers
    # ------------------------------------------------------------------ #

    def _map_relationship_stance(
        self,
        c: PersonalizationConstraints,
        tipi: dict[str, float],
        ecrrs: dict[str, float],
        project: dict[str, float],
    ) -> None:
        avoidance = ecrrs.get("attachment_avoidance", 0.5)
        anxiety = ecrrs.get("attachment_anxiety", 0.5)
        warmth_tol = project.get("warmth_tolerance", 0.5)
        directness = project.get("directness_preference", 0.5)
        disagree_tol = project.get("disagreement_tolerance", 0.5)

        # Attachment style: complement subject's insecurity pattern
        attachment_preferred: list[str] = []
        if avoidance >= 0.55:
            # Subject avoidant → Gumi securely attached, warm, reachable
            attachment_preferred = ["secure attachment", "earned secure"]
        elif anxiety >= 0.55:
            # Subject anxious → Gumi calm, bounded (does NOT mirror anxiety)
            attachment_preferred = ["secure attachment", "earned secure"]
            c.relationship_stance.excluded.append("anxious attachment")
        else:
            # Secure subject → gentle distinctiveness
            attachment_preferred = ["earned secure", "secure attachment"]

        # Intimacy comfort: calibrated to subject's warmth tolerance
        intimacy_preferred: list[str] = []
        if warmth_tol >= 0.6:
            intimacy_preferred = ["open to intimacy", "selective intimacy"]
        elif warmth_tol <= 0.35:
            intimacy_preferred = ["guarded with intimacy", "selective intimacy"]
        else:
            intimacy_preferred = ["selective intimacy", "intimacy as growth area"]

        # Conflict style: match subject's directness preference for complementarity
        conflict_preferred: list[str] = []
        if directness >= 0.6:
            conflict_preferred = ["confronts directly", "constructive conflict style"]
        elif disagree_tol <= 0.35:
            conflict_preferred = ["mediates for others", "avoids conflict"]
        else:
            conflict_preferred = ["constructive conflict style", "mediates for others"]

        c.relationship_stance.preferred = attachment_preferred + intimacy_preferred + conflict_preferred
        c.relationship_stance.weight = 0.8

    def _map_boundaries(
        self,
        c: PersonalizationConstraints,
        tipi: dict[str, float],
        project: dict[str, float],
    ) -> None:
        autonomy_tol = project.get("gumi_autonomy_tolerance", 0.5)
        emotional_tol = project.get("emotional_intensity_tolerance", 0.5)
        emotional_stability = tipi.get("emotional_stability", 0.5)

        personal_preferred: list[str] = []
        if autonomy_tol >= 0.6:
            personal_preferred = ["strong personal boundaries", "context-dependent boundaries"]
        elif autonomy_tol <= 0.35:
            personal_preferred = ["flexible boundaries", "permeable boundaries"]
        else:
            personal_preferred = ["context-dependent boundaries", "boundary work in progress"]

        energy_preferred: list[str] = []
        extraversion = tipi.get("extraversion", 0.5)
        # Complement subject extraversion: introverted subject → Gumi more extroverted
        if extraversion <= 0.35:
            energy_preferred = ["extroverted energy management", "balanced energy management"]
        elif extraversion >= 0.65:
            energy_preferred = ["introverted energy management", "balanced energy management"]
        else:
            energy_preferred = ["balanced energy management"]

        c.boundaries.preferred = personal_preferred + energy_preferred
        c.boundaries.weight = 0.7

    def _map_passions(
        self,
        c: PersonalizationConstraints,
        tipi: dict[str, float],
        project: dict[str, float],
    ) -> None:
        openness = tipi.get("openness", 0.5)

        # High openness subject → Gumi can have creative/artistic passions (similarity aids connection)
        # Low openness → Gumi more conventional, practical interests
        if openness >= 0.6:
            c.passions.preferred = [
                "creative arts", "reading and writing", "music and performance",
                "travel and exploration", "nature and gardening",
            ]
        elif openness <= 0.35:
            c.passions.preferred = [
                "sports and fitness", "cooking and food", "crafts and DIY",
                "technology and gaming", "collecting",
            ]
        # Mid openness: no strong constraint
        c.passions.weight = 0.5

    def _map_social_world(
        self,
        c: PersonalizationConstraints,
        project: dict[str, float],
    ) -> None:
        others_tol = project.get("gumi_has_others_tolerance", 0.5)

        if others_tol >= 0.6:
            # Subject comfortable with Gumi having others → richer social world
            c.social_world.preferred = [
                "close-knit circle", "wide acquaintance network",
                "close extended family",
            ]
        elif others_tol <= 0.35:
            # Subject uncomfortable with Gumi's others → minimal, understated
            c.social_world.preferred = [
                "few trusted friends", "chosen family bonds",
                "few workplace connections",
            ]
        c.social_world.weight = 0.6

    def _map_routine(
        self,
        c: PersonalizationConstraints,
        project: dict[str, float],
    ) -> None:
        low_freq = project.get("low_frequency_preference", 0.5)
        continuity = project.get("continuity_preference", 0.5)

        if low_freq >= 0.6:
            # Subject prefers fewer contacts → Gumi has structured, bounded routine
            c.routine.preferred = ["structured routine", "flexible schedule"]
        elif low_freq <= 0.35:
            c.routine.preferred = ["social-centric", "flexible schedule"]

        if continuity >= 0.6:
            # Subject values continuity → Gumi has stable, patterned daily pattern
            if "structured routine" not in c.routine.preferred:
                c.routine.preferred.insert(0, "structured routine")

        c.routine.weight = 0.5

    def _map_identity(
        self,
        c: PersonalizationConstraints,
        subject_baseline: dict[str, Any],
    ) -> None:
        """Exclude exact matches from subject on family_structure (anti-clone)."""
        self_report = subject_baseline.get("self_report_fields", {})
        researcher = subject_baseline.get("researcher_coded_fields", {})

        subject_family = (
            self_report.get("family_structure", {}).get("value")
            or researcher.get("family_structure", {}).get("value")
        )
        if subject_family:
            c.identity.excluded = [str(subject_family)]
            c.identity.weight = 0.9

    def _map_place(
        self,
        c: PersonalizationConstraints,
        subject_baseline: dict[str, Any],
    ) -> None:
        """Exclude exact location match (anti-clone)."""
        self_report = subject_baseline.get("self_report_fields", {})
        researcher = subject_baseline.get("researcher_coded_fields", {})

        subject_location = (
            self_report.get("location", {}).get("value")
            or researcher.get("location", {}).get("value")
        )
        if subject_location:
            c.place.excluded = [str(subject_location)]
            c.place.weight = 0.9

    def _map_life_role(
        self,
        c: PersonalizationConstraints,
        subject_baseline: dict[str, Any],
    ) -> None:
        """Exclude exact occupation match (anti-clone)."""
        self_report = subject_baseline.get("self_report_fields", {})
        researcher = subject_baseline.get("researcher_coded_fields", {})

        subject_occ = (
            self_report.get("occupation_or_study", {}).get("value")
            or researcher.get("occupation_or_study", {}).get("value")
        )
        if subject_occ:
            c.life_role.excluded = [str(subject_occ)]
            c.life_role.weight = 0.9

    # ------------------------------------------------------------------ #
    # Sweet-spot target
    # ------------------------------------------------------------------ #

    def _compute_sweet_spot_target(
        self,
        tipi: dict[str, float],
        ecrrs: dict[str, float],
        project: dict[str, float],
    ) -> float:
        """Derive desired similarity target (0.3–0.7 range).

        Higher IOS desired closeness → higher similarity target.
        Higher avoidance / lower warmth → lower similarity target.
        """
        ios = project.get("desired_initial_closeness", 0.5)
        warmth = project.get("warmth_tolerance", 0.5)
        avoidance = ecrrs.get("attachment_avoidance", 0.5)

        # Blend: more closeness wanted → higher target; more avoidance → lower
        raw = 0.4 + 0.2 * ios + 0.1 * warmth - 0.1 * avoidance
        return round(max(0.3, min(0.7, raw)), 3)
