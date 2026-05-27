"""Tests for gender-aware pronoun conforming of persona templates.

The persona templates are authored with feminine pronouns; the conformer
rewrites the final text so masculine and non-binary personas do not refer to
themselves with the wrong pronouns (the bug that made masculine "Sam" speak of
itself as a woman).
"""

from relic.gumi.llm_narrator import _conform_persona_pronouns, _persona_pronouns


def test_feminine_and_empty_are_noops():
    text = "She lives here. Her work is hard. She knows herself."
    assert _conform_persona_pronouns(text, "feminine") == text
    assert _conform_persona_pronouns(text, "") == text
    assert _persona_pronouns("feminine") is None
    assert _persona_pronouns("") is None


def test_masculine_flips_pronouns_verb_safe():
    src = (
        "She presents as masculine. Her background is rich. "
        "She never invites the subject to visit her. She draws from her world. "
        "Sam should fit her character."
    )
    out = _conform_persona_pronouns(src, "masculine")
    assert "She" not in out and "Her" not in out
    assert " her " not in f" {out} " and "herself" not in out
    assert "He presents as masculine." in out
    assert "His background is rich." in out
    # object "her" after a verb becomes "him", not possessive "his"
    assert "visit him" in out
    assert "from his world" in out
    assert "fit his character" in out


def test_masculine_keeps_singular_verb_conjugation():
    # he/she share 3rd-person singular conjugation, so verbs are untouched
    out = _conform_persona_pronouns("She maintains limits. She has a world.", "masculine")
    assert out == "He maintains limits. He has a world."


def test_nonconforming_uses_singular_they_with_verb_agreement():
    src = "She maintains limits. She is curious. She has a world. She does not help. Her voice is warm."
    out = _conform_persona_pronouns(src, "gender non-conforming")
    assert "They maintain limits." in out
    assert "They are curious." in out
    assert "They have a world." in out
    assert "They do not help." in out
    assert "Their voice is warm." in out


def test_does_not_touch_unrelated_words():
    # word boundaries must not corrupt "here", "there", "gather", "other"
    out = _conform_persona_pronouns("She is here, there, gathering with the others.", "masculine")
    assert "here" in out and "there" in out and "gathering" in out and "others" in out
    assert out.startswith("He is here")
