"""Candidate retrieval metrics for an EXHAUSTIVELY labeled, bounded pair universe."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Evaluation:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None


def evaluate_candidates(result, true_pairs):
    """true_pairs contains all true (left source ID, right source ID) links in these inputs.

    Missing positive labels are treated as negatives, so partially reviewed samples
    must not be passed to this function. This evaluates retrieval, not casualty truth.
    """
    truth = set(true_pairs)
    left_ids = {r.source_id for r in result.left}
    right_ids = {r.source_id for r in result.right}
    if any(a not in left_ids or b not in right_ids for a, b in truth):
        raise ValueError("truth contains source IDs outside the evaluation datasets")
    proposed = {(c.left.source_id, c.right.source_id) for c in result.candidates}
    tp = len(proposed & truth)
    fp = len(proposed - truth)
    fn = len(truth - proposed)
    return Evaluation(tp, fp, fn, tp / (tp + fp) if tp + fp else None, tp / (tp + fn) if tp + fn else None)
