"""Generation modes for Gumi background profiles: random, manual, and hybrid."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, TYPE_CHECKING

from relic.gumi.background_generator import (
    GumiBackgroundGenerator,
    GumiBackgroundProfile,
    GenerationMode,
)

if TYPE_CHECKING:
    from relic.gumi.personalization import PersonalizationConstraints


@dataclass
class GenerationReport:
    """Report documenting the generation process and results."""
    subject_id: str
    generation_mode: str
    random_seed: int | None
    sampler_version: str
    input_profile_hash: str
    sampled_fields: list[str]
    rejected_candidates: list[dict]
    final_candidate: dict
    sweet_spot_score: float
    risk_flags: list[str]
    created_at: str


class GenerationModeRunner:
    """Runner for different Gumi background generation modes."""

    SAMPLER_VERSION = "1.0.0"

    def __init__(self):
        self._generator = GumiBackgroundGenerator()

    def _compute_input_hash(self, subject_profile: dict) -> str:
        """Compute deterministic SHA256 hash of input profile."""
        profile_str = str(sorted(subject_profile.items()))
        return hashlib.sha256(profile_str.encode()).hexdigest()

    def _timestamp(self) -> str:
        """Generate ISO timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _flatten_domains(self, profile: GumiBackgroundProfile) -> dict[str, Any]:
        """Flatten domains into a single dict for storage."""
        result = {"subject_id": profile.subject_id}
        for domain_name, domain_data in profile.domains.items():
            if isinstance(domain_data, dict):
                for key, value in domain_data.items():
                    result[f"{domain_name}_{key}"] = value
            else:
                result[domain_name] = domain_data
        return result

    def run_random(
        self,
        subject_profile: dict,
        seed: int | None = None,
        personalization: "PersonalizationConstraints | None" = None,
    ) -> tuple[GumiBackgroundProfile, GenerationReport]:
        """Generate profile using random sampling with reproducible seed."""
        input_hash = self._compute_input_hash(subject_profile)
        rejected_candidates: list[dict] = []
        max_retries = 10

        for attempt in range(max_retries):
            profile = self._generator.generate(
                subject_profile=subject_profile,
                mode=GenerationMode.RANDOM,
                seed=seed,
                personalization=personalization,
            )
            risk_flags = self.check_risk(profile, subject_profile)

            if "occupation_mirror" in risk_flags or "location_mirror" in risk_flags:
                rejected_candidates.append({
                    "profile": self._flatten_domains(profile),
                    "risk_flags": risk_flags,
                    "sweet_spot_score": self.compute_sweet_spot_score(
                        profile, subject_profile, personalization
                    ),
                })
                continue

            sweet_spot = self.compute_sweet_spot_score(profile, subject_profile, personalization)
            sampled_fields = list(profile.provenance.keys())

            return profile, GenerationReport(
                subject_id=profile.subject_id,
                generation_mode="random",
                random_seed=seed,
                sampler_version=self.SAMPLER_VERSION,
                input_profile_hash=input_hash,
                sampled_fields=sampled_fields,
                rejected_candidates=rejected_candidates,
                final_candidate=self._flatten_domains(profile),
                sweet_spot_score=sweet_spot,
                risk_flags=risk_flags,
                created_at=self._timestamp(),
            )

        profile = self._generator.generate(
            subject_profile=subject_profile,
            mode=GenerationMode.RANDOM,
            seed=seed,
            personalization=personalization,
        )
        return profile, GenerationReport(
            subject_id=profile.subject_id,
            generation_mode="random",
            random_seed=seed,
            sampler_version=self.SAMPLER_VERSION,
            input_profile_hash=input_hash,
            sampled_fields=list(profile.provenance.keys()),
            rejected_candidates=rejected_candidates,
            final_candidate=self._flatten_domains(profile),
            sweet_spot_score=self.compute_sweet_spot_score(profile, subject_profile, personalization),
            risk_flags=self.check_risk(profile, subject_profile),
            created_at=self._timestamp(),
        )

    def run_manual(
        self,
        subject_profile: dict,
        field_values: dict,
    ) -> tuple[GumiBackgroundProfile, GenerationReport]:
        """Generate profile with manually specified field values."""
        input_hash = self._compute_input_hash(subject_profile)
        subject_id = subject_profile.get("subject_id", "unknown")

        profile = self._generator.generate(
            subject_profile=subject_profile,
            mode=GenerationMode.MANUAL,
            manual_overrides=field_values,
        )

        sweet_spot = self.compute_sweet_spot_score(profile, subject_profile)
        risk_flags = self.check_risk(profile, subject_profile)

        return profile, GenerationReport(
            subject_id=profile.subject_id,
            generation_mode="manual",
            random_seed=None,
            sampler_version=self.SAMPLER_VERSION,
            input_profile_hash=input_hash,
            sampled_fields=[],
            rejected_candidates=[],
            final_candidate=self._flatten_domains(profile),
            sweet_spot_score=sweet_spot,
            risk_flags=risk_flags,
            created_at=self._timestamp(),
        )

    def run_hybrid(
        self,
        subject_profile: dict,
        seed: int | None = None,
        researcher_overrides: dict | None = None,
        personalization: "PersonalizationConstraints | None" = None,
    ) -> tuple[GumiBackgroundProfile, GenerationReport]:
        """Generate profile with random base and researcher overrides."""
        input_hash = self._compute_input_hash(subject_profile)
        researcher_overrides = researcher_overrides or {}
        rejected_candidates: list[dict] = []

        for attempt in range(10):
            base_profile = self._generator.generate(
                subject_profile=subject_profile,
                mode=GenerationMode.HYBRID,
                seed=seed,
                personalization=personalization,
            )
            risk_flags = self.check_risk(base_profile, subject_profile)

            if "occupation_mirror" in risk_flags or "location_mirror" in risk_flags:
                rejected_candidates.append({
                    "profile": self._flatten_domains(base_profile),
                    "risk_flags": risk_flags,
                })
                continue

            break

        domains = dict(base_profile.domains)
        provenance = dict(base_profile.provenance)
        generated_values: dict[str, Any] = {}

        for field_name, override_value in researcher_overrides.items():
            generated_values[field_name] = domains.get(field_name)
            domains[field_name] = override_value
            provenance[field_name] = "hybrid"

        profile = GumiBackgroundProfile(
            subject_id=base_profile.subject_id,
            generation_mode="hybrid",
            profile_version=1,
            domains=domains,
            provenance=provenance,
            anti_clone_checked=False,
            created_at=self._timestamp(),
            random_seed=seed,
        )

        final_candidate = self._flatten_domains(profile)
        for field_name in researcher_overrides:
            final_candidate[f"{field_name}_generated_value"] = generated_values.get(field_name)
            final_candidate[f"{field_name}_final_value"] = researcher_overrides[field_name]

        sweet_spot = self.compute_sweet_spot_score(profile, subject_profile, personalization)
        risk_flags = self.check_risk(profile, subject_profile)

        sampled_fields = [k for k, v in provenance.items() if v == "generated"]

        return profile, GenerationReport(
            subject_id=profile.subject_id,
            generation_mode="hybrid",
            random_seed=seed,
            sampler_version=self.SAMPLER_VERSION,
            input_profile_hash=input_hash,
            sampled_fields=sampled_fields,
            rejected_candidates=rejected_candidates,
            final_candidate=final_candidate,
            sweet_spot_score=sweet_spot,
            risk_flags=risk_flags,
            created_at=self._timestamp(),
        )

    def compute_sweet_spot_score(
        self,
        gumi_profile: GumiBackgroundProfile,
        subject_profile: dict,
        personalization: "PersonalizationConstraints | None" = None,
    ) -> float:
        """Compute sweet-spot score between generated Gumi profile and subject.

        Uses a 7-component formula derived from:
        - Similarity where trust and comprehension matter (Aron & Aron 1996)
        - Complementarity in attachment and agency (Wiggins 1979 IPC)
        - Distinctness in occupation/location/family (anti-clone rule)
        - Stabilization: Gumi must NOT mirror subject vulnerability

        Returns: 0.0-1.0 where 1.0 is optimal sweet spot.
        """
        if personalization is not None:
            return self._compute_7component_score(gumi_profile, subject_profile, personalization)
        return self._compute_legacy_score(gumi_profile, subject_profile)

    def _compute_7component_score(
        self,
        gumi_profile: GumiBackgroundProfile,
        subject_profile: dict,
        personalization: "PersonalizationConstraints",
    ) -> float:
        """Full 7-component sweet-spot formula.

        Components and weights:
          C1 (0.20) Openness similarity, shared curiosity aids connection
          C2 (0.25) Attachment complementarity, Gumi stable where subject insecure
          C3 (0.20) Distinctness, occupation/location/family differ
          C4 (0.15) Stabilization, Gumi does not mirror anxiety/avoidance
          C5 (0.10) Autonomy fit, Gumi's boundary profile matches subject tolerance
          C6 (0.05) Desired-closeness fit, relationship_stance aligns with IOS target
          C7 (0.05) Passions overlap, some shared interests for connection
        """
        tipi = personalization.tipi
        ecrrs = personalization.ecrrs
        project = personalization.project
        domains = gumi_profile.domains

        # C1: openness similarity (0.20)
        subject_openness = tipi.get("openness", 0.5)
        gumi_passions = domains.get("passions", {})
        creative_interests = {"creative arts", "reading and writing", "music and performance", "travel and exploration"}
        gumi_primary = set(gumi_passions.get("primary_interests", []))
        gumi_creative_ratio = len(gumi_primary & creative_interests) / max(len(gumi_primary), 1)
        c1 = 1.0 - abs(subject_openness - gumi_creative_ratio)

        # C2: attachment complementarity (0.25)
        avoidance = ecrrs.get("attachment_avoidance", 0.5)
        anxiety = ecrrs.get("attachment_anxiety", 0.5)
        gumi_stance = domains.get("relationship_stance", {})
        gumi_attachment = gumi_stance.get("attachment_style", "")
        secure_styles = {"secure attachment", "earned secure"}
        gumi_is_secure = gumi_attachment in secure_styles
        subject_insecure = avoidance >= 0.5 or anxiety >= 0.5
        if subject_insecure and gumi_is_secure:
            c2 = 1.0
        elif not subject_insecure:
            c2 = 0.7  # secure subject, any Gumi style acceptable, slight bonus
        else:
            c2 = 0.2  # insecure subject + insecure Gumi = poor complement

        # C3: distinctness (0.20), penalize mirrors on occupation/location/family
        gumi_life_role = domains.get("life_role", {})
        gumi_occ = gumi_life_role.get("occupation_or_study", "")
        gumi_place = domains.get("place", {})
        gumi_loc = gumi_place.get("location", "")
        gumi_identity = domains.get("identity", {})
        gumi_family = gumi_identity.get("family_structure", "")
        _sr3 = subject_profile.get("self_report_fields", {})
        subject_occ = (
            subject_profile.get("occupation_or_study")
            or (_sr3.get("occupation_or_study") or {}).get("value", "")
        )
        subject_loc = (
            subject_profile.get("location")
            or (_sr3.get("location") or {}).get("value", "")
        )
        subject_family = (
            subject_profile.get("family_structure")
            or (_sr3.get("family_structure") or {}).get("value", "")
        )

        mirrors = sum([
            bool(subject_occ and gumi_occ == subject_occ),
            bool(subject_loc and gumi_loc == subject_loc),
            bool(subject_family and gumi_family == subject_family),
        ])
        c3 = max(0.0, 1.0 - mirrors * 0.5)

        # C4: stabilization (0.15), Gumi must not mirror vulnerability
        gumi_boundary = domains.get("boundaries", {})
        gumi_personal = gumi_boundary.get("personal_space", "")
        gumi_energy = gumi_boundary.get("energy_management", "")
        stable_indicators = {"strong personal boundaries", "context-dependent boundaries",
                             "balanced energy management", "energy boundaries around work"}
        unstable_indicators = {"permeable boundaries", "boundary work in progress"}
        gumi_stable = (gumi_personal in stable_indicators or gumi_energy in stable_indicators)
        gumi_unstable = (gumi_personal in unstable_indicators)
        subject_vulnerable = anxiety >= 0.55 or avoidance >= 0.65
        if subject_vulnerable and gumi_stable:
            c4 = 1.0
        elif subject_vulnerable and gumi_unstable:
            c4 = 0.1
        else:
            c4 = 0.7

        # C5: autonomy fit (0.10)
        autonomy_tol = project.get("gumi_autonomy_tolerance", 0.5)
        gumi_has_strong_bounds = gumi_personal in {"strong personal boundaries", "context-dependent boundaries"}
        if autonomy_tol >= 0.6 and gumi_has_strong_bounds:
            c5 = 1.0
        elif autonomy_tol <= 0.35 and not gumi_has_strong_bounds:
            c5 = 1.0
        elif autonomy_tol >= 0.6 and not gumi_has_strong_bounds:
            c5 = 0.4
        else:
            c5 = 0.7

        # C6: desired-closeness fit (0.05), IOS target vs relationship_stance warmth
        ios = project.get("desired_initial_closeness", 0.5)
        gumi_intimacy = gumi_stance.get("intimacy_comfort", "")
        open_styles = {"open to intimacy"}
        selective_styles = {"selective intimacy", "intimacy as growth area"}
        guarded_styles = {"guarded with intimacy"}
        if ios >= 0.65 and gumi_intimacy in open_styles:
            c6 = 1.0
        elif 0.35 < ios < 0.65 and gumi_intimacy in selective_styles:
            c6 = 1.0
        elif ios <= 0.35 and gumi_intimacy in guarded_styles:
            c6 = 1.0
        else:
            c6 = 0.4

        # C7: passions overlap (0.05), some shared interests aids connection
        _sr = subject_profile.get("self_report_fields", {})
        _ip = subject_profile.get("interaction_preferences", {})
        _raw_interests = (
            subject_profile.get("interests")
            or _ip.get("preferred_topics")
            or [v.get("value") for v in _sr.values() if isinstance(v, dict) and isinstance(v.get("value"), str)]
        )
        subject_interests = set(x for x in _raw_interests if isinstance(x, str)) if _raw_interests else set()
        gumi_hobbies = set(gumi_passions.get("hobbies", []))
        if subject_interests and (gumi_primary | gumi_hobbies):
            overlap = len(subject_interests & (gumi_primary | gumi_hobbies))
            total = len(subject_interests | gumi_primary | gumi_hobbies)
            c7 = min(1.0, overlap / max(total, 1) * 3)  # scale up partial overlap
        else:
            c7 = 0.5  # no data: neutral

        score = (
            0.20 * c1 +
            0.25 * c2 +
            0.20 * c3 +
            0.15 * c4 +
            0.10 * c5 +
            0.05 * c6 +
            0.05 * c7
        )
        return round(max(0.0, min(1.0, score)), 4)

    def _compute_legacy_score(
        self,
        gumi_profile: GumiBackgroundProfile,
        subject_profile: dict,
    ) -> float:
        """Legacy 4-factor similarity score used when personalization is unavailable."""
        similarities = []

        gumi_life_role = gumi_profile.domains.get("life_role", {})
        gumi_occupation = gumi_life_role.get("occupation_or_study", "")
        gumi_place = gumi_profile.domains.get("place", {})
        gumi_location = gumi_place.get("location", "")

        _sr_leg = subject_profile.get("self_report_fields", {})
        subject_occupation = (
            subject_profile.get("occupation_or_study")
            or (_sr_leg.get("occupation_or_study") or {}).get("value", "")
        )
        subject_location = (
            subject_profile.get("location")
            or (_sr_leg.get("location") or {}).get("value", "")
        )
        subject_family = (
            subject_profile.get("family_structure")
            or (_sr_leg.get("family_structure") or {}).get("value", "")
        )

        if subject_occupation and gumi_occupation == subject_occupation:
            similarities.append(1.0)
        elif subject_occupation and gumi_occupation:
            similarities.append(0.5)
        else:
            similarities.append(0.0)

        if subject_location and gumi_location == subject_location:
            similarities.append(1.0)
        elif subject_location and gumi_location:
            similarities.append(0.5)
        else:
            similarities.append(0.0)

        gumi_identity = gumi_profile.domains.get("identity", {})
        gumi_family = gumi_identity.get("family_structure", "")

        if subject_family and gumi_family == subject_family:
            similarities.append(1.0)
        elif subject_family and gumi_family:
            similarities.append(0.5)
        else:
            similarities.append(0.0)

        gumi_passions = gumi_profile.domains.get("passions", {})
        gumi_interests = set(gumi_passions.get("primary_interests", []))
        _sr2 = subject_profile.get("self_report_fields", {})
        _ip2 = subject_profile.get("interaction_preferences", {})
        _raw2 = (
            subject_profile.get("interests")
            or _ip2.get("preferred_topics")
            or []
        )
        subject_interests = set(_raw2) if _raw2 else set()

        if subject_interests and gumi_interests:
            intersection = len(gumi_interests & subject_interests)
            union = len(gumi_interests | subject_interests)
            similarities.append(intersection / union if union > 0 else 0.0)
        else:
            similarities.append(0.0)

        raw = sum(similarities) / len(similarities) if similarities else 0.5
        if raw > 0.9:
            return 0.9
        if raw < 0.1:
            return 0.1
        return max(0.0, min(1.0, (raw - 0.3) / 0.5))

    def check_risk(
        self,
        gumi_profile: GumiBackgroundProfile,
        subject_profile: dict,
    ) -> list[str]:
        """Check for risk flags in generated profile."""
        flags: list[str] = []
        
        sweet_spot_score = self.compute_sweet_spot_score(gumi_profile, subject_profile)
        
        if sweet_spot_score > 0.9:
            flags.append("high_similarity")
        if sweet_spot_score < 0.1:
            flags.append("low_relatability")
        
        gumi_life_role = gumi_profile.domains.get("life_role", {})
        gumi_occupation = gumi_life_role.get("occupation_or_study", "")
        subject_occupation = subject_profile.get("occupation_or_study", "")
        
        if subject_occupation and gumi_occupation == subject_occupation:
            flags.append("occupation_mirror")
        
        gumi_place = gumi_profile.domains.get("place", {})
        gumi_location = gumi_place.get("location", "")
        subject_location = subject_profile.get("location", "")
        
        if subject_location and gumi_location == subject_location:
            flags.append("location_mirror")
        
        return flags
