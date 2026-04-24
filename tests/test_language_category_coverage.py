"""Coverage tests for the `language` facet category.

The v3.0 schema adds `language.verbal_complexity` (see CPIS whitepaper §12,
'Representational coverage'). The profile bridge and question engine must
treat it like any other category rather than letting it fall through to
generic fallbacks.
"""
import importlib
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "relic"))


@pytest.fixture
def profile_bridge():
    return importlib.import_module("relic_profile_bridge")


@pytest.fixture
def question_engine():
    return importlib.import_module("relic_question_engine")


def test_profile_bridge_maps_language_category(profile_bridge) -> None:
    """CATEGORY_MAP must expose `language`; else language traits fall back
    to the generic 'conoscenze_assimilate' bucket, hiding them from
    category-aware consumers."""
    assert "language" in profile_bridge.CATEGORY_MAP, (
        "language category missing from CATEGORY_MAP - verbal_complexity "
        "traits would silently map to the generic fallback"
    )


def test_profile_bridge_displays_language_category(profile_bridge) -> None:
    """CATEGORY_DISPLAY must have a human-readable label for `language`."""
    assert "language" in profile_bridge.CATEGORY_DISPLAY
    label = profile_bridge.CATEGORY_DISPLAY["language"]
    assert label and label != "language", "display label must not be the raw key"


def test_profile_md_iterates_language_category(profile_bridge) -> None:
    """generate_profile_md's iteration order must include `language`, so a
    populated verbal_complexity trait actually appears in the artifact."""
    source = Path(profile_bridge.__file__).read_text(encoding="utf-8")
    # The function builds a tuple of categories to iterate; 'language' must
    # be among them.
    assert '"language"' in source, (
        "generate_profile_md must include language in its category iteration"
    )


def test_question_engine_weights_language_importance(question_engine) -> None:
    """CATEGORY_IMPORTANCE must include `language` with a designed weight
    rather than the generic 0.50 fallback from `dict.get(..., 0.50)`."""
    weights = question_engine.CATEGORY_IMPORTANCE
    assert "language" in weights, (
        "language missing from CATEGORY_IMPORTANCE - FGS falls back to "
        "an undesigned 0.50 default"
    )
    w = weights["language"]
    assert 0.30 <= w <= 0.90, f"unexpected weight for language: {w}"


def test_total_facets_fallback_matches_current_schema(profile_bridge) -> None:
    """generate_profile_md falls back on a hardcoded total-facet count when
    the summary is missing. It must not reference the v1.0 value of 46."""
    source = Path(profile_bridge.__file__).read_text(encoding="utf-8")
    assert 'total_facets", 46' not in source, (
        "legacy fallback of 46 facets; update to reflect the current schema"
    )
