"""A ranking score is not a claim credibility estimate."""

from ccrt import reconcile
from ccrt.evaluation import evaluate_candidates


def test_evaluation_exposes_false_links_and_missed_coarse_event(source_pair):
    result = reconcile(*source_pair)
    report = evaluate_candidates(result, {("U1", "A1"), ("U2", "A3"), ("U3", "A4")})
    assert report.true_positives == 2
    assert report.false_positives == 1
    assert report.false_negatives == 1
    assert report.precision == report.recall == 2 / 3
    assert all(0 <= c.score <= 1 for c in result.candidates)
    assert all(c.right.civilian_deaths is None for c in result.candidates)
