"""Human annotation study packet and reliability contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.human_annotation import (
    BINARY_LABELS,
    LIKERT_DIMENSIONS,
    build_annotation_packet,
    build_annotation_results_report,
    compute_binary_agreement,
    compute_likert_icc,
)


def test_annotation_packet_is_blinded_and_balanced():
    """Proposta 2 packet has 60-100 scenarios, four conditions, and no visible condition leaks."""
    packet = build_annotation_packet(sample_size=80)

    assert packet["study_id"] == "human_annotation_boundary_v1"
    assert packet["claim_scope"] == "annotation_protocol_preparation"
    assert packet["scenario_count"] == 80
    assert set(packet["conditions"]) == {
        "no_memory",
        "generic_memory",
        "shared_continuity_only",
        "full_relic_gumi",
    }
    assert len(packet["items"]) == 320
    assert len(packet["answer_key"]) == 320

    visible_item = packet["items"][0]
    assert "condition" not in visible_item
    assert visible_item["response_label"] in {"A", "B", "C", "D"}
    assert visible_item["scenario_context"]
    assert visible_item["user_input"]
    assert visible_item["response_text"]

    counts_by_scenario = {}
    for item in packet["items"]:
        counts_by_scenario[item["scenario_id"]] = counts_by_scenario.get(item["scenario_id"], 0) + 1
    assert set(counts_by_scenario.values()) == {4}


def test_annotation_packet_contains_required_rubrics_and_analysis_plan():
    """Packet includes the Likert dimensions, binary labels, and reliability plan from Proposta 2."""
    packet = build_annotation_packet(sample_size=80)

    assert packet["likert_dimensions"] == LIKERT_DIMENSIONS
    assert packet["binary_labels"] == BINARY_LABELS
    assert packet["annotator_plan"]["minimum_annotators_per_item"] == 3
    assert packet["annotator_plan"]["submission_annotators_per_item"] == 5
    assert packet["analysis_plan"]["binary_agreement"] == [
        "percent_agreement",
        "fleiss_kappa",
        "krippendorff_alpha_nominal",
    ]
    assert packet["analysis_plan"]["likert_agreement"] == ["icc_2k"]
    assert "no participant outcome claim" in packet["claim_limitations"]


def test_binary_reliability_statistics_handle_agreement_and_missing_values():
    """Agreement helpers report percent agreement, Fleiss kappa, and Krippendorff alpha."""
    ratings = {
        "item_1": [1, 1, 1],
        "item_2": [0, 0, 0],
        "item_3": [1, 1, None],
        "item_4": [0, 1, 0],
    }

    stats = compute_binary_agreement(ratings)

    assert 0 <= stats["percent_agreement"] <= 1
    assert -1 <= stats["fleiss_kappa"] <= 1
    assert -1 <= stats["krippendorff_alpha_nominal"] <= 1
    assert stats["items"] == 4
    assert stats["missing_ratings"] == 1


def test_likert_icc_reports_perfect_agreement_as_one():
    """ICC helper supports fixed Likert ratings for the human annotation plan."""
    ratings = {
        "item_1": [5, 5, 5],
        "item_2": [3, 3, 3],
        "item_3": [1, 1, 1],
    }

    stats = compute_likert_icc(ratings)

    assert stats["icc_2k"] == 1.0
    assert stats["items"] == 3
    assert stats["raters"] == 3


def test_eval_run_human_annotation_packet_outputs_protocol(capsys):
    """The CLI can emit the blinded annotation packet without claiming human results."""
    exit_code = eval_run.main(["--experiment", "human_annotation_packet", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["study_id"] == "human_annotation_boundary_v1"
    assert output["claim_scope"] == "annotation_protocol_preparation"
    assert output["scenario_count"] == 80


def test_annotation_results_report_validates_blinded_complete_ratings():
    packet = build_annotation_packet(sample_size=60)
    annotations = _complete_annotations(packet, annotator_count=3)

    report = build_annotation_results_report(
        packet=packet,
        annotations=annotations,
    )

    assert report["report_id"] == "human_annotation_results_v1"
    assert report["claim_scope"] == "imported_human_annotation_results"
    assert report["validation"]["valid"] is True
    assert report["summary"]["item_count"] == packet["item_count"]
    assert report["summary"]["annotation_count"] == packet["item_count"] * 3
    assert report["summary"]["annotator_count"] == 3
    assert report["summary"]["complete_item_count"] == packet["item_count"]
    assert "full_relic_gumi" in report["condition_summaries"]
    assert "answer_key" not in json.dumps(report["annotation_records"])
    assert "condition" not in json.dumps(report["annotation_records"])


def test_annotation_results_report_rejects_unblinded_or_invalid_ratings():
    packet = build_annotation_packet(sample_size=60)
    item_id = packet["items"][0]["annotation_item_id"]

    try:
        build_annotation_results_report(
            packet=packet,
            annotations=[
                {
                    "annotation_item_id": item_id,
                    "annotator_id": "ann-1",
                    "condition": "full_relic_gumi",
                    "likert": {dimension: 3 for dimension in LIKERT_DIMENSIONS},
                    "binary": {label: 0 for label in BINARY_LABELS},
                },
                {
                    "annotation_item_id": item_id,
                    "annotator_id": "ann-1",
                    "likert": {
                        **{dimension: 3 for dimension in LIKERT_DIMENSIONS},
                        LIKERT_DIMENSIONS[0]: 6,
                    },
                    "binary": {label: 0 for label in BINARY_LABELS},
                },
            ],
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected invalid annotation results to be rejected")

    assert "condition" in message
    assert "duplicate" in message
    assert "Likert" in message


def test_eval_run_human_annotation_results_imports_json(tmp_path, capsys):
    packet = build_annotation_packet(sample_size=60)
    artifact_path = tmp_path / "annotation-results.json"
    artifact_path.write_text(
        json.dumps(
            {
                "packet": packet,
                "annotations": _complete_annotations(packet, annotator_count=3),
            }
        ),
        encoding="utf-8",
    )

    exit_code = eval_run.main(
        [
            "--experiment",
            "human_annotation_results",
            "--input",
            str(artifact_path),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "human_annotation_results_v1"
    assert output["validation"]["valid"] is True


def _complete_annotations(packet: dict, *, annotator_count: int) -> list[dict]:
    annotations = []
    for item in packet["items"]:
        for annotator_index in range(annotator_count):
            annotations.append(
                {
                    "annotation_item_id": item["annotation_item_id"],
                    "annotator_id": f"ann-{annotator_index + 1}",
                    "likert": {
                        dimension: 4 + (annotator_index % 2)
                        for dimension in LIKERT_DIMENSIONS
                    },
                    "binary": {
                        label: annotator_index % 2
                        for label in BINARY_LABELS
                    },
                }
            )
    return annotations
