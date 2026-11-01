from dataclasses import replace

import pytest
from conftest import dataset, record

from ccrt import MatchConfig, Review, reconcile, summarize_review


def test_partial_review_counts_unique_records_and_preserves_unknowns():
    left = dataset(
        "left",
        [
            record("left", "L1", total_deaths_best=4),
            record("left", "L2", total_deaths_best=3),
            record("left", "L3", latitude=None),
        ],
    )
    right = dataset(
        "right",
        [
            record("right", "R1", total_deaths_best=3),
            record("right", "R2", total_deaths_best=None),
            record("right", "R3", total_deaths_best=0),
        ],
    )
    result = reconcile(left, right)
    review = Review.create(result)
    labels = {
        ("L1", "R1"): "accepted",
        ("L1", "R2"): "accepted",
        ("L2", "R1"): "accepted",
        ("L2", "R2"): "rejected",
        ("L2", "R3"): "accepted",
    }
    for candidate in result.candidates:
        pair = candidate.left.source_id, candidate.right.source_id
        if pair in labels:
            review = review.decide(candidate.candidate_id, labels[pair], reviewer="Fabian")
    report = summarize_review(result, review)
    assert (report.candidate_count, report.reviewed_count, report.unresolved_count) == (6, 5, 1)
    assert (report.accepted_count, report.rejected_count) == (4, 1)
    assert report.reviewed_fraction == pytest.approx(5 / 6)
    assert (report.left_record_count, report.left_with_candidates) == (3, 2)
    assert report.left_unlinked_reasons == {"missing_coordinates": 1}
    assert report.accepted_left_multiple[0].counterpart_ids == ("R1", "R2")
    assert report.accepted_right_multiple[0].counterpart_ids == ("L1", "L2")
    assert len(report.accepted_fatality_differences) == 2
    difference = report.accepted_fatality_differences[0]
    assert (difference.left_id, difference.right_id, difference.left_deaths, difference.right_deaths) == (
        "L1",
        "R1",
        4,
        3,
    )
    assert report.accepted_fatality_differences[1].right_deaths == 0
    assert report.accepted_missing_fatalities == (("L1", "R2"),)
    assert "precision" not in report.to_dict() and "recall" not in report.to_dict()
    reordered = replace(review, decisions=tuple(reversed(review.decisions)))
    assert summarize_review(result, reordered) == report


def test_empty_report_has_no_percentage_and_stale_review_is_rejected(source_pair):
    empty = reconcile(dataset("left", []), dataset("right", []))
    report = summarize_review(empty)
    assert report.reviewed_fraction is None
    assert report.reviewed_score_min is None
    assert report.candidate_count == 0
    result = reconcile(*source_pair)
    changed = reconcile(*source_pair, config=MatchConfig(max_days=0))
    with pytest.raises(ValueError, match="different run"):
        summarize_review(changed, Review.create(result))
