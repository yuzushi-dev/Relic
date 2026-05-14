"""Tests: domain-derived visual/voice/lyria canons and wardrobe generation."""
from __future__ import annotations

from relic.profile.registry import (
    _derive_visual_canon,
    _derive_voice_canon,
    _derive_lyria_canon,
    _derive_wardrobe,
)
from relic.gumi_plugin.tts import select_voice_for_canon


class TestDeriveVisualCanon:
    def test_coastal_city_palette(self) -> None:
        visual = _derive_visual_canon(
            1,
            place={"location": "coastal city"},
            passions={},
            embodiment={},
            life_role={},
            routine={},
        )
        assert "sea green" in visual["palette"]

    def test_passion_motifs_included(self) -> None:
        visual = _derive_visual_canon(
            1,
            place={},
            passions={"primary_interests": ["reading and writing"]},
            embodiment={},
            life_role={},
            routine={},
        )
        assert any("book" in m or "note" in m for m in visual["motifs"])

    def test_feminine_style(self) -> None:
        visual = _derive_visual_canon(
            1,
            place={},
            passions={},
            embodiment={"gender_expression": "feminine"},
            life_role={},
            routine={},
        )
        assert visual["style"] == "soft naturalism"

    def test_wardrobe_has_five_sets(self) -> None:
        visual = _derive_visual_canon(
            1,
            place={"location": "urban center", "housing_situation": "rents apartment"},
            passions={"primary_interests": ["creative arts"]},
            embodiment={"gender_expression": "feminine"},
            life_role={"occupation_or_study": "artist"},
            routine={},
        )
        assert len(visual["wardrobe"]) == 5

    def test_wardrobe_set_names(self) -> None:
        wardrobe = _derive_wardrobe(
            place={},
            passions={},
            embodiment={},
            life_role={},
            palette=["warm gray"],
        )
        names = [s["set_name"] for s in wardrobe]
        assert "giornata quotidiana" in names
        assert "contesto speciale" in names

    def test_wardrobe_occupation_influences_daily(self) -> None:
        wardrobe = _derive_wardrobe(
            place={},
            passions={},
            embodiment={},
            life_role={"occupation_or_study": "artist"},
            palette=["warm gray"],
        )
        daily = next(s for s in wardrobe if s["set_name"] == "giornata quotidiana")
        assert any("overall" in p or "oversized" in p for p in daily["key_pieces"])

    def test_wardrobe_passion_influences_weekend(self) -> None:
        wardrobe = _derive_wardrobe(
            place={},
            passions={"primary_interests": ["nature and gardening"]},
            embodiment={},
            life_role={},
            palette=["warm gray"],
        )
        weekend = next(s for s in wardrobe if s["set_name"] == "weekend creativo")
        assert any("cargo" in p or "stivali" in p for p in weekend["key_pieces"])


class TestDeriveVoiceCanon:
    def test_feminine_voice_profile(self) -> None:
        voice = _derive_voice_canon(
            embodiment={"gender_expression": "feminine"},
            relationship_stance={},
        )
        assert "warm" in voice["voice_profile"]

    def test_masculine_voice_profile(self) -> None:
        voice = _derive_voice_canon(
            embodiment={"gender_expression": "masculine"},
            relationship_stance={},
        )
        assert "calm" in voice["voice_profile"] or "direct" in voice["voice_profile"]

    def test_anxious_attachment_bright_timbre(self) -> None:
        voice = _derive_voice_canon(
            embodiment={},
            relationship_stance={"attachment_style": "anxious attachment"},
        )
        assert "bright" in voice["timbre"]

    def test_guarded_intimacy_measured_pace(self) -> None:
        voice = _derive_voice_canon(
            embodiment={},
            relationship_stance={"intimacy_comfort": "guarded with intimacy"},
        )
        assert voice["pace"] == "measured"


class TestDerivelyriaCa:
    def test_secure_attachment_mood(self) -> None:
        lyria = _derive_lyria_canon(
            passions={},
            relationship_stance={"attachment_style": "secure attachment"},
            routine={},
        )
        assert any("warm" in m or "grounded" in m for m in lyria["mood_palette"])

    def test_night_owl_instrumentation(self) -> None:
        lyria = _derive_lyria_canon(
            passions={},
            relationship_stance={},
            routine={"daily_schedule": "night owl"},
        )
        assert "dark pads" in lyria["instrumentation"]

    def test_early_riser_instrumentation(self) -> None:
        lyria = _derive_lyria_canon(
            passions={},
            relationship_stance={},
            routine={"daily_schedule": "early riser"},
        )
        assert "light strings" in lyria["instrumentation"]

    def test_music_preferences_in_references(self) -> None:
        lyria = _derive_lyria_canon(
            passions={"music_preferences": ["jazz", "ambient"]},
            relationship_stance={},
            routine={},
        )
        assert "jazz" in lyria["references"]


class TestSelectVoiceForCanon:
    def test_feminine_secure_returns_aoede(self) -> None:
        bg = {
            "domains": {
                "embodiment": {"gender_expression": "feminine"},
                "relationship_stance": {"attachment_style": "secure attachment"},
            }
        }
        assert select_voice_for_canon(bg) == "Aoede"

    def test_masculine_avoidant_returns_fenrir(self) -> None:
        bg = {
            "domains": {
                "embodiment": {"gender_expression": "masculine"},
                "relationship_stance": {"attachment_style": "avoidant attachment"},
            }
        }
        assert select_voice_for_canon(bg) == "Fenrir"

    def test_androgynous_defaults_kore(self) -> None:
        bg = {
            "domains": {
                "embodiment": {"gender_expression": "androgynous"},
                "relationship_stance": {},
            }
        }
        assert select_voice_for_canon(bg) == "Kore"

    def test_empty_background_fallback(self) -> None:
        assert select_voice_for_canon({}) == "Kore"
