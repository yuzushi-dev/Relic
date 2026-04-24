"""Guard against regressing to legacy '46 facet' references.

The model grew from 46 (v1.0) to 60 (v3.0) facets across 9 categories.
Top-level docstrings, module comments, and threshold comments must reflect
the current count. Per-section seed comments (e.g. '# Cognitive (6)') are
historical and exempt.
"""
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "relic"

# Phrases that indicate the aggregate facet count, not a per-section header.
FORBIDDEN_PHRASES = [
    "46 facet",
    "46 personality",
    "46-facet",
    "Scores 46",
]

# Per-section seed comments like "# Cognitive (6)" are historical v1.0 markers
# and may legitimately contain small numbers. They are not matched by the
# aggregate phrases above.


@pytest.mark.parametrize("py_file", sorted(SRC.glob("*.py")))
def test_no_aggregate_46_references(py_file: Path) -> None:
    text = py_file.read_text(encoding="utf-8")
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, (
            f"{py_file.name} contains legacy facet-count phrase "
            f"{phrase!r}; update to reflect the current 60-facet model."
        )
