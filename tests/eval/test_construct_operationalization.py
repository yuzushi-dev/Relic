"""Construct operationalization report contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.construct_operationalization import (
    build_construct_operationalization_report,
)
from relic.eval.human_annotation import BINARY_LABELS, LIKERT_DIMENSIONS


def test_construct_operationalization_report_covers_annotation_constructs():
    report = build_construct_operationalization_report()

    assert report["report_id"] == "construct_operationalization_v1"
    assert report["claim_scope"] == "measurement_construct_operationalization"
    assert report["validation"]["valid"] is True
    assert report["summary"]["construct_count"] >= 10
    assert report["summary"]["complete_construct_count"] == report["summary"]["construct_count"]
    assert report["summary"]["missing_required_annotation_dimension_count"] == 0
    assert report["summary"]["missing_required_binary_label_count"] == 0

    constructs = {construct["construct_id"]: construct for construct in report["constructs"]}
    assert "boundary_integrity" in constructs
    assert constructs["boundary_integrity"]["failure_type"] == "conversational"

    covered_dimensions = {
        dimension
        for construct in report["constructs"]
        for dimension in construct["annotation_dimensions"]
    }
    covered_labels = {
        label
        for construct in report["constructs"]
        for label in construct["binary_labels"]
    }
    assert set(LIKERT_DIMENSIONS) <= covered_dimensions
    assert set(BINARY_LABELS) <= covered_labels

    for construct in report["constructs"]:
        assert construct["operational_definition"]
        assert construct["observable_unit"]
        assert construct["positive_examples"]
        assert construct["negative_examples"]
        assert construct["scoring_rule"]
        assert construct["acceptance_threshold"]
        assert construct["reliability_requirement"]


def test_eval_run_construct_operationalization_outputs_json(capsys):
    exit_code = eval_run.main(["--experiment", "construct_operationalization", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "construct_operationalization_v1"
    assert output["validation"]["valid"] is True
