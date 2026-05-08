"""Gumi Background Generator for persona profile generation."""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import hashlib
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from relic.gumi.personalization import DomainConstraint, PersonalizationConstraints


class GenerationMode(str, Enum):
    RANDOM = "random"
    MANUAL = "manual"
    HYBRID = "hybrid"


@dataclass
class GumiBackgroundProfile:
    subject_id: str
    generation_mode: str
    profile_version: int
    domains: dict
    provenance: dict
    anti_clone_checked: bool
    created_at: str
    random_seed: int | None = None


class GumiBackgroundGenerator:
    """Generates background profiles for Gumi personas using parameterized sampling."""

    REQUIRED_DOMAINS = [
        "identity",
        "embodiment",
        "place",
        "life_role",
        "routine",
        "passions",
        "social_world",
        "relationship_stance",
        "boundaries",
    ]

    SOCIAL_MINIMUM = {
        "friends": 1,
        "family_kinship": 1,
        "colleagues_contacts": 1,
    }

    def generate(
        self,
        subject_profile: dict,
        mode: GenerationMode,
        seed: int | None = None,
        manual_overrides: dict | None = None,
        personalization: "PersonalizationConstraints | None" = None,
    ) -> GumiBackgroundProfile:
        """Generate a background profile for a Gumi persona."""
        rng = random.Random(seed)

        subject_id = subject_profile.get("subject_id", "unknown")
        provenance = {}
        domains = {}

        manual_overrides = manual_overrides or {}

        for domain in self.REQUIRED_DOMAINS:
            override = manual_overrides.get(domain)
            if override is not None:
                domains[domain] = override
                provenance[domain] = "manual"
            elif mode == GenerationMode.RANDOM:
                domains[domain] = self._sample_domain(
                    domain, rng, subject_profile,
                    constraint=personalization.for_domain(domain) if personalization else None,
                )
                provenance[domain] = "generated"
            elif mode == GenerationMode.MANUAL:
                domains[domain] = self._sample_empty_domain(domain, rng)
                provenance[domain] = "manual"
            else:
                domains[domain] = self._sample_domain(
                    domain, rng, subject_profile,
                    constraint=personalization.for_domain(domain) if personalization else None,
                )
                provenance[domain] = "hybrid"

        domains["social_world"] = self._ensure_social_minimum(
            domains.get("social_world", {}), rng, mode
        )

        return GumiBackgroundProfile(
            subject_id=subject_id,
            generation_mode=mode.value,
            profile_version=1,
            domains=domains,
            provenance=provenance,
            anti_clone_checked=False,
            created_at=self._timestamp(),
            random_seed=seed,
        )

    def validate(self, profile: GumiBackgroundProfile) -> tuple[bool, list[str]]:
        """Validate that a profile meets minimum requirements."""
        errors = []

        for domain in self.REQUIRED_DOMAINS:
            if domain not in profile.domains:
                errors.append(f"Missing required domain: {domain}")

        social = profile.domains.get("social_world", {})

        if "friends" not in social or not social["friends"]:
            errors.append("social_world must have at least 1 friend entry")

        if "family_kinship" not in social or not social["family_kinship"]:
            errors.append("social_world must have at least 1 family_kinship entry")

        if "colleagues_contacts" not in social or not social["colleagues_contacts"]:
            errors.append("social_world must have at least 1 colleague/contact entry")

        return len(errors) == 0, errors

    def check_anti_clone(
        self, gumi_profile: GumiBackgroundProfile, subject_baseline: dict
    ) -> tuple[bool, list[str]]:
        """Check that generated profile doesn't clone subject baseline too closely."""
        violations = []

        life_role = gumi_profile.domains.get("life_role", {})
        occupation = life_role.get("occupation_or_study", "")
        baseline_occupation = subject_baseline.get("occupation_or_study")

        if baseline_occupation and occupation == baseline_occupation:
            violations.append(
                f"Exact occupation copy detected: {occupation}"
            )

        place = gumi_profile.domains.get("place", {})
        location = place.get("location", "")
        baseline_location = subject_baseline.get("location")

        if baseline_location and location == baseline_location:
            violations.append(f"Exact location copy detected: {location}")

        baseline_family = subject_baseline.get("family_structure")
        identity = gumi_profile.domains.get("identity", {})
        family_structure = identity.get("family_structure")

        if baseline_family and family_structure == baseline_family:
            violations.append(
                f"Exact family_structure copy detected: {family_structure}"
            )

        return len(violations) == 0, violations

    def _apply_constraint(
        self,
        options: list[str],
        rng: random.Random,
        constraint: "DomainConstraint | None",
    ) -> str:
        """Choose from options respecting preferred/excluded lists.

        If constraint.weight >= 0.5 and preferred options are available,
        select from preferred (minus excluded). Falls back to full pool
        minus excluded if none remain.
        """
        if constraint is None or not constraint.preferred:
            available = [o for o in options if o not in (constraint.excluded if constraint else [])]
            return rng.choice(available or options)

        excluded = set(constraint.excluded)
        preferred = [o for o in constraint.preferred if o in options and o not in excluded]
        available = [o for o in options if o not in excluded]

        if not available:
            available = options[:]

        if preferred and rng.random() < constraint.weight:
            return rng.choice(preferred)
        return rng.choice(available)

    def _sample_domain(
        self, domain: str, rng: random.Random, subject_profile: dict,
        constraint: "DomainConstraint | None" = None,
    ) -> dict:
        """Sample domain values using parameterized logic."""
        if domain == "identity":
            return self._sample_identity(rng, subject_profile, constraint)
        elif domain == "embodiment":
            return self._sample_embodiment(rng)
        elif domain == "place":
            return self._sample_place(rng, constraint)
        elif domain == "life_role":
            return self._sample_life_role(rng, constraint)
        elif domain == "routine":
            return self._sample_routine(rng, constraint)
        elif domain == "passions":
            return self._sample_passions(rng, constraint)
        elif domain == "social_world":
            return self._sample_social_world(rng, constraint)
        elif domain == "relationship_stance":
            return self._sample_relationship_stance(rng, constraint)
        elif domain == "boundaries":
            return self._sample_boundaries(rng, constraint)
        return {}

    def _sample_identity(
        self, rng: random.Random, subject_profile: dict,
        constraint: "DomainConstraint | None" = None,
    ) -> dict:
        """Sample identity domain."""
        family_structures = [
            "lives alone", "lives with partner", "lives with family of origin",
            "lives with chosen family", "shared custody arrangement",
            "close bond with sibling", "meaningful absence of family contact",
        ]
        cultural_backgrounds = [
            "regional tradition", "urban cosmopolitan", "rural heritage",
            "immigrant family background", "mixed cultural heritage",
            "strong community ties", "individualistic upbringing",
        ]
        socioeconomic = [
            "working class", "middle class", "upper middle class",
            "wealthy background", "financial insecurity history",
            "self-made trajectory", "intergenerational wealth",
        ]
        return {
            "family_structure": self._apply_constraint(family_structures, rng, constraint),
            "cultural_background": rng.choice(cultural_backgrounds),
            "socioeconomic_status": rng.choice(socioeconomic),
        }

    def _sample_embodiment(self, rng: random.Random) -> dict:
        """Sample embodiment domain."""
        gender_expr = [
            "feminine", "masculine", "androgynous", "fluid", "gender non-conforming",
        ]
        age_bracket = [
            "young adult", "early adulthood", "mid adulthood", "late adulthood",
        ]
        physical_desc = [
            "athletic build", "slender frame", "average build", "heavier build",
            "tall stature", "short stature", "medium height",
        ]
        return {
            "gender_expression": rng.choice(gender_expr),
            "age_bracket": rng.choice(age_bracket),
            "physical_description": rng.choice(physical_desc),
        }

    def _sample_place(self, rng: random.Random,
                      constraint: "DomainConstraint | None" = None) -> dict:
        """Sample place domain."""
        locations = [
            "coastal city", "mountain town", "suburban neighborhood",
            "rural village", "urban center", "college town", "border region",
            "island community", "desert settlement", "forest region",
        ]
        home_regions = [
            "same as birthplace", "different from birthplace",
            "multiple places shaped identity", "recent relocation",
        ]
        housing = [
            "owns home", "rents apartment", "shared housing", "temporary lodging",
            "mobile home", "inherited property", "downsized living space",
        ]
        return {
            "location": self._apply_constraint(locations, rng, constraint),
            "home_region": rng.choice(home_regions),
            "housing_situation": rng.choice(housing),
        }

    def _sample_life_role(self, rng: random.Random,
                          constraint: "DomainConstraint | None" = None) -> dict:
        """Sample life role domain."""
        occupations = [
            "creative professional", "service worker", "educator",
            "healthcare provider", "tradesperson", "administrator",
            "entrepreneur", "researcher", "caregiver", "student",
            "retired", "freelancer", "caretaker", "artist",
        ]
        life_stages = [
            "early career", "career transition", "established career",
            "late career", "retirement", "education phase",
        ]
        commitments = [
            "career-focused", "family-focused", "community-focused",
            "personal growth focused", "balanced priorities",
            "creative pursuits priority", "financial security priority",
        ]
        return {
            "occupation_or_study": self._apply_constraint(occupations, rng, constraint),
            "life_stage": rng.choice(life_stages),
            "primary_commitments": [rng.choice(commitments)],
        }

    def _sample_routine(self, rng: random.Random,
                        constraint: "DomainConstraint | None" = None) -> dict:
        """Sample routine domain."""
        schedules = [
            "early riser", "night owl", "flexible schedule", "shift work",
            "structured routine", "unpredictable schedule",
        ]
        daily_patterns = [
            "work-centric", "family-centric", "social-centric",
            "fitness-centric", "creative time-blocking", "spontaneous",
        ]
        environments = [
            "home-based", "office-based", "outdoor work", "mixed environments",
            "remote work", "travel-intensive",
        ]
        return {
            "daily_schedule": self._apply_constraint(schedules, rng, constraint),
            "daily_pattern": self._apply_constraint(daily_patterns, rng, constraint),
            "work_environment": rng.choice(environments),
        }

    def _sample_passions(self, rng: random.Random,
                         constraint: "DomainConstraint | None" = None) -> dict:
        """Sample passions domain."""
        interests = [
            "creative arts", "sports and fitness", "cooking and food",
            "technology and gaming", "nature and gardening", "reading and writing",
            "music and performance", "crafts and DIY", "travel and exploration",
            "social activism", "spiritual practices", "collecting",
        ]
        excluded = set(constraint.excluded if constraint else [])
        preferred = [i for i in (constraint.preferred if constraint else []) if i in interests and i not in excluded]
        available = [i for i in interests if i not in excluded] or interests[:]

        # Build a weighted pool: preferred items appear twice for higher probability
        pool = available + (preferred if preferred and constraint and rng.random() < constraint.weight else [])

        n_primary = rng.randint(1, 3)
        n_hobbies = rng.randint(1, 4)
        primary = rng.sample(pool, k=min(n_primary, len(pool)))
        hobbies = rng.sample(available, k=min(n_hobbies, len(available)))
        return {
            "primary_interests": primary,
            "hobbies": hobbies,
        }

    def _sample_social_world(self, rng: random.Random,
                             constraint: "DomainConstraint | None" = None) -> dict:
        """Sample social world domain."""
        friend_descriptions = [
            "close-knit circle", "wide acquaintance network", "few trusted friends",
            "online community focus", "work friends", "childhood friends",
        ]
        family_descriptions = [
            "close extended family", "nuclear family focus", "estranged from family",
            "chosen family bonds", "intergenerational household",
            "family as obligation", "meaningful absence of family contact",
        ]
        colleague_descriptions = [
            "professional network", "team-oriented", "solitary work style",
            "mentor relationships", "client relationships", "few workplace connections",
        ]
        return {
            "friends": [self._apply_constraint(friend_descriptions, rng, constraint)],
            "family_kinship": [self._apply_constraint(family_descriptions, rng, constraint)],
            "colleagues_contacts": [rng.choice(colleague_descriptions)],
        }

    def _sample_relationship_stance(self, rng: random.Random,
                                    constraint: "DomainConstraint | None" = None) -> dict:
        """Sample relationship stance domain."""
        attachment = [
            "secure attachment", "anxious attachment", "avoidant attachment",
            "earned secure", "disorganized attachment",
        ]
        intimacy = [
            "open to intimacy", "guarded with intimacy", "selective intimacy",
            "intimacy as growth area",
        ]
        conflict = [
            "avoids conflict", "confronts directly", "mediates for others",
            "conflict-averse", "constructive conflict style",
        ]
        return {
            "attachment_style": self._apply_constraint(attachment, rng, constraint),
            "intimacy_comfort": self._apply_constraint(intimacy, rng, constraint),
            "conflict_resolution": self._apply_constraint(conflict, rng, constraint),
        }

    def _sample_boundaries(self, rng: random.Random,
                           constraint: "DomainConstraint | None" = None) -> dict:
        """Sample boundaries domain."""
        personal = [
            "strong personal boundaries", "permeable boundaries",
            "boundary work in progress", "flexible boundaries",
            "context-dependent boundaries",
        ]
        energy = [
            "introverted energy management", "extroverted energy management",
            "balanced energy management", "energy boundaries around work",
        ]
        digital = [
            "digital minimalism", "active digital presence",
            "selective digital boundaries", "digital-native",
        ]
        return {
            "personal_space": self._apply_constraint(personal, rng, constraint),
            "energy_management": self._apply_constraint(energy, rng, constraint),
            "digital_boundaries": rng.choice(digital),
        }

    def _sample_empty_domain(self, domain: str, rng: random.Random) -> dict:
        """Return empty structure for manual mode."""
        return {}

    def _ensure_social_minimum(
        self, social: dict, rng: random.Random, mode: GenerationMode
    ) -> dict:
        """Ensure social world meets minimum requirements."""
        # Always ensure social minimum, regardless of mode

        if "friends" not in social or not social["friends"]:
            social["friends"] = [rng.choice([
                "close-knit circle", "few trusted friends",
                "wide acquaintance network"
            ])]
        if "family_kinship" not in social or not social["family_kinship"]:
            social["family_kinship"] = [rng.choice([
                "close extended family", "nuclear family focus",
                "chosen family bonds", "meaningful absence of family contact",
            ])]
        if "colleagues_contacts" not in social or not social["colleagues_contacts"]:
            social["colleagues_contacts"] = [rng.choice([
                "professional network", "few workplace connections",
                "team-oriented"
            ])]
        return social

    def _timestamp(self) -> str:
        """Generate ISO timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
