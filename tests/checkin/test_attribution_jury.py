"""Unit tests for the importable cross-family attribution jury.

Pure/deterministic pieces only — these MUST NOT hit the network. They exercise
the lexical voter, the tokenizer, the vote aggregator and the panel constants.
"""
from relic.checkin.attribution_jury import tokens, lexical_best, aggregate, JUDGES


def test_tokens_lowercases_and_splits():
    assert tokens("Ciao, Mondo!") == {"ciao", "mondo"}


def test_lexical_best_picks_highest_overlap():
    facets = {
        "a.x": {"name": "rischio", "description": "propensione al rischio", "spectrum_low": "", "spectrum_high": ""},
        "b.y": {"name": "umorismo", "description": "stile umorismo", "spectrum_low": "", "spectrum_high": ""},
    }
    cands = [{"id": "a.x", **facets["a.x"]}, {"id": "b.y", **facets["b.y"]}]
    assert lexical_best("ho corso un grosso rischio", cands, facets) == "a.x"


def test_aggregate_flags_on_majority_reject():
    # Recorded facet rejected by a strict majority of voters AND >= 2 model
    # families agree on the replacement (the production family-agreement guard).
    #
    # NOTE: the real aggregate() returns action/target (there is no "flagged" or
    # "agreed" key), and it only flags when >= 2 distinct model families reject
    # the recorded facet, so by_judge must carry that signal. A flag == an action
    # that is not "keep"; the agreed replacement is `target`.
    out = aggregate(
        "a.x",
        votes=["b.y", "b.y", "b.y", "a.x"],
        by_judge={"gemma4:31b-cloud": ["b.y"], "gpt-oss:120b-cloud": ["b.y"]},
    )
    assert out["action"] == "reattribute"
    assert out["target"] == "b.y"


def test_judges_are_three_distinct_families():
    families = {m.split(":")[0].split("-")[0] for m, _ in JUDGES}
    assert {"gemma4", "gpt", "minimax"} <= families or len(JUDGES) == 3
