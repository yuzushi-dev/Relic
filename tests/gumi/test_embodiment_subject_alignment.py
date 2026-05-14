"""Tests: gender_identity + age_range inform _sample_embodiment (anti-clone + complement)."""
from __future__ import annotations

import pytest

from relic.gumi.background_generator import GumiBackgroundGenerator


GEN = GumiBackgroundGenerator()


class TestGenderComplement:
    def _gender(self, gender_val: str, seed: int = 1) -> str:
        import random
        profile = {"self_report_fields": {"gender_identity": {"value": gender_val}}}
        result = GEN._sample_embodiment(random.Random(seed), profile)
        return result["gender_expression"]

    def test_male_subject_gets_non_masculine(self) -> None:
        for seed in range(20):
            assert self._gender("male", seed) != "masculine", \
                f"seed {seed}: masculine returned for male subject"

    def test_female_subject_gets_non_feminine(self) -> None:
        for seed in range(20):
            assert self._gender("female", seed) != "feminine", \
                f"seed {seed}: feminine returned for female subject"

    def test_non_binary_gets_full_pool(self) -> None:
        results = {self._gender("non-binary", s) for s in range(30)}
        # non-binary subject → full pool, multiple genders should appear
        assert len(results) > 1

    def test_unknown_gender_uses_full_pool(self) -> None:
        import random
        profile = {"self_report_fields": {"gender_identity": {"value": "prefer not to say"}}}
        results = {GEN._sample_embodiment(random.Random(s), profile)["gender_expression"] for s in range(20)}
        assert len(results) > 1

    def test_no_profile_uses_full_pool(self) -> None:
        import random
        results = {GEN._sample_embodiment(random.Random(s), None)["gender_expression"] for s in range(20)}
        assert len(results) > 1


class TestAgeAntiClone:
    def _age(self, age_val: str, seed: int = 1) -> str:
        import random
        profile = {"self_report_fields": {"age_range": {"value": age_val}}}
        result = GEN._sample_embodiment(random.Random(seed), profile)
        return result["age_bracket"]

    def test_young_adult_excluded_for_18_24(self) -> None:
        for seed in range(20):
            assert self._age("18-24", seed) != "young adult", f"seed {seed}"

    def test_mid_adulthood_excluded_for_35_44(self) -> None:
        for seed in range(20):
            assert self._age("35-44", seed) != "mid adulthood", f"seed {seed}"

    def test_unknown_age_uses_full_pool(self) -> None:
        import random
        profile = {"self_report_fields": {"age_range": {"value": ""}}}
        results = {GEN._sample_embodiment(random.Random(s), profile)["age_bracket"] for s in range(20)}
        assert len(results) > 1
