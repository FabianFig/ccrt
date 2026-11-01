"""Descriptive review diagnostics for partially or fully reviewed candidates."""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from ccrt._version import __version__
from ccrt.review import Review
from ccrt.schema import digest


@dataclass(frozen=True)
class MultipleAcceptedLinks:
    source_id: str
    counterpart_ids: tuple[str, ...]


@dataclass(frozen=True)
class FatalityDifference:
    left_id: str
    right_id: str
    left_deaths: int
    right_deaths: int


@dataclass(frozen=True)
class ReviewReport:
    run_id: str
    review_fingerprint: str
    candidate_count: int
    reviewed_count: int
    accepted_count: int
    rejected_count: int
    unresolved_count: int
    reviewed_fraction: float | None
    reviewed_without_notes: int
    reviewed_score_min: float | None
    reviewed_score_max: float | None
    left_source: str
    right_source: str
    left_record_count: int
    right_record_count: int
    left_with_candidates: int
    right_with_candidates: int
    left_unlinked_reasons: dict[str, int]
    right_unlinked_reasons: dict[str, int]
    accepted_left_multiple: tuple[MultipleAcceptedLinks, ...]
    accepted_right_multiple: tuple[MultipleAcceptedLinks, ...]
    accepted_fatality_differences: tuple[FatalityDifference, ...]
    accepted_missing_fatalities: tuple[tuple[str, str], ...]

    def to_dict(self):
        """JSON-ready diagnostics, with no raw accounts or casualty aggregation."""
        return {
            "kind": "review-report",
            "schema_version": 1,
            "ccrt_version": __version__,
            "scope": "generated candidates only; coverage is not matching accuracy",
            **asdict(self),
        }


def summarize_review(result, review=None):
    """Summarize decisions without treating unresolved pairs as negative labels.

    Multiple accepted counterparts and differing fatality claims are descriptive
    checks, not proof of an incorrect link. Missed links outside the candidate
    set are unknown, so this function does not calculate precision or recall.
    """
    review = review if review is not None else Review.create(result)
    review.validate(result)
    decisions = {decision.candidate_id: decision for decision in review.decisions}
    counts = Counter(decision.status for decision in review.decisions)
    reviewed = [c for c in result.candidates if decisions[c.candidate_id].status != "unresolved"]
    accepted = [c for c in result.candidates if decisions[c.candidate_id].status == "accepted"]
    left_links, right_links = defaultdict(set), defaultdict(set)
    differences, missing = [], []
    for candidate in accepted:
        left, right = candidate.left, candidate.right
        left_links[left.source_id].add(right.source_id)
        right_links[right.source_id].add(left.source_id)
        a, b = left.total_deaths_best, right.total_deaths_best
        if a is None or b is None:
            missing.append((left.source_id, right.source_id))
        elif a != b:
            differences.append(FatalityDifference(left.source_id, right.source_id, a, b))

    def multiple(groups):
        return tuple(
            MultipleAcceptedLinks(source_id, tuple(sorted(counterparts)))
            for source_id, counterparts in sorted(groups.items())
            if len(counterparts) > 1
        )

    def unlinked_reasons(source):
        return dict(sorted(Counter(u.reason for u in result.unlinked if u.record.source == source).items()))

    scores = [c.score for c in reviewed]
    return ReviewReport(
        run_id=result.run_id,
        review_fingerprint=digest(
            {
                "run_id": review.run_id,
                "decisions": sorted((asdict(d) for d in review.decisions), key=lambda d: d["candidate_id"]),
            }
        ),
        candidate_count=len(result.candidates),
        reviewed_count=len(reviewed),
        accepted_count=counts["accepted"],
        rejected_count=counts["rejected"],
        unresolved_count=counts["unresolved"],
        reviewed_fraction=len(reviewed) / len(result.candidates) if result.candidates else None,
        reviewed_without_notes=sum(d.status != "unresolved" and not d.note.strip() for d in review.decisions),
        reviewed_score_min=min(scores) if scores else None,
        reviewed_score_max=max(scores) if scores else None,
        left_source=result.left.source,
        right_source=result.right.source,
        left_record_count=len(result.left),
        right_record_count=len(result.right),
        left_with_candidates=len({c.left.key for c in result.candidates}),
        right_with_candidates=len({c.right.key for c in result.candidates}),
        left_unlinked_reasons=unlinked_reasons(result.left.source),
        right_unlinked_reasons=unlinked_reasons(result.right.source),
        accepted_left_multiple=multiple(left_links),
        accepted_right_multiple=multiple(right_links),
        accepted_fatality_differences=tuple(sorted(differences, key=lambda d: (d.left_id, d.right_id))),
        accepted_missing_fatalities=tuple(sorted(missing)),
    )


def format_review_report(report):
    """Compact CLI summary; the JSON report retains all diagnostic IDs."""
    fraction = f" ({report.reviewed_fraction:.1%})" if report.reviewed_fraction is not None else ""
    lines = [
        f"Reviewed {report.reviewed_count}/{report.candidate_count} candidate links{fraction}",
        f"{report.accepted_count} accepted, {report.rejected_count} rejected, {report.unresolved_count} unresolved",
        f"{report.reviewed_without_notes} decided links have no review note",
        "",
        "Source records with candidates:",
        f"  {report.left_source}: {report.left_with_candidates}/{report.left_record_count}",
        f"  {report.right_source}: {report.right_with_candidates}/{report.right_record_count}",
    ]
    for source, reasons in (
        (report.left_source, report.left_unlinked_reasons),
        (report.right_source, report.right_unlinked_reasons),
    ):
        if reasons:
            lines.append(f"  {source} unlinked: " + ", ".join(f"{k}={v}" for k, v in reasons.items()))
    lines.extend(["", "Accepted links with multiple counterparts (allowed):"])
    for source, groups in (
        (report.left_source, report.accepted_left_multiple),
        (report.right_source, report.accepted_right_multiple),
    ):
        lines.append(f"  {source}: {len(groups)} records")
        for group in groups[:5]:
            lines.append(f"    {group.source_id}: {', '.join(group.counterpart_ids)}")
        if len(groups) > 5:
            lines.append(f"    {len(groups) - 5} more; see JSON report")
    lines.extend(
        [
            "",
            f"Different reported fatality counts: {len(report.accepted_fatality_differences)} accepted links",
            f"Missing fatality counts: {len(report.accepted_missing_fatalities)} accepted links",
        ]
    )
    if report.reviewed_score_min is not None:
        lines.append(
            f"Reviewed score range: {report.reviewed_score_min:.3f} to {report.reviewed_score_max:.3f}"
        )
    lines.append("\nCoverage describes generated candidates. Matching accuracy needs exhaustive labels.")
    return "\n".join(lines)
