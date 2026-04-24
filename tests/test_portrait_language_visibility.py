"""The Layer 4 portrait must surface the `language.verbal_complexity`
Layer 2 trait alongside the Layer 3 idiolect metrics, not bury it behind
the generic top-25-by-confidence trait cutoff.

Option B from the language-visibility discussion: one additional line
inside the existing Idiolect section, so Layer 2 and Layer 3 linguistic
signals appear side by side in the artifact agents actually see
(`PORTRAIT.md`).
"""
import importlib
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "relic"))


@pytest.fixture
def portrait():
    return importlib.import_module("relic_portrait")


def test_format_verbal_complexity_line_exists(portrait) -> None:
    assert hasattr(portrait, "format_verbal_complexity_line"), (
        "expected a dedicated formatter so the portrait can integrate "
        "the language trait with the idiolect section"
    )


def test_format_verbal_complexity_returns_none_when_trait_missing(portrait) -> None:
    assert portrait.format_verbal_complexity_line(None) is None
    assert portrait.format_verbal_complexity_line({}) is None


def test_format_verbal_complexity_returns_none_below_threshold(portrait) -> None:
    trait = {
        "value_position": 0.6,
        "confidence": 0.20,
        "spectrum_low": "semplice",
        "spectrum_high": "ricco",
    }
    assert portrait.format_verbal_complexity_line(trait) is None, (
        "below the 0.30 reporting threshold the line must not be rendered"
    )


def test_format_verbal_complexity_line_renders_when_confident(portrait) -> None:
    trait = {
        "value_position": 0.72,
        "confidence": 0.55,
        "spectrum_low": "semplice",
        "spectrum_high": "ricco",
    }
    line = portrait.format_verbal_complexity_line(trait)
    assert line is not None
    assert "Verbal complexity" in line
    assert "0.55" in line or "conf=0.55" in line
    assert "ricco" in line  # pole label should reflect the high side


def test_load_portrait_data_exposes_language_trait(portrait, tmp_path) -> None:
    """load_portrait_data must surface the language.verbal_complexity trait
    under a dedicated key, independent of the top-25 slice used for the
    global trait list."""
    import sqlite3

    db_path = tmp_path / "mini.db"
    db = sqlite3.connect(str(db_path))
    db.executescript("""
        CREATE TABLE facets (id TEXT PRIMARY KEY, name TEXT, category TEXT,
                             spectrum_low TEXT, spectrum_high TEXT);
        CREATE TABLE traits (facet_id TEXT, value_position REAL,
                             confidence REAL, status TEXT);
        INSERT INTO facets VALUES
          ('language.verbal_complexity', 'verbal_complexity', 'language',
           'semplice', 'ricco');
        INSERT INTO traits VALUES
          ('language.verbal_complexity', 0.7, 0.55, 'active');
    """)
    db.commit()

    row = portrait.fetch_verbal_complexity(db)
    assert row is not None
    assert row["value_position"] == pytest.approx(0.7)
    assert row["confidence"] == pytest.approx(0.55)


def test_build_prompt_idiolect_section_includes_language_line(portrait) -> None:
    """When the data dict carries a `verbal_complexity` entry, the rendered
    prompt must mention the line inside the idiolect area."""
    trait = {
        "value_position": 0.72,
        "confidence": 0.55,
        "spectrum_low": "semplice",
        "spectrum_high": "ricco",
    }
    line = portrait.format_verbal_complexity_line(trait)
    assert line is not None
    assert "Verbal complexity" in line
