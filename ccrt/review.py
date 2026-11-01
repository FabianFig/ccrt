"""Explicit review decisions bound to a reproducible candidate run."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from ccrt.merge import Reconciliation


@dataclass(frozen=True)
class Decision:
    candidate_id: str
    status: str = "unresolved"
    reviewer: str = ""
    note: str = ""
    reviewed_at: str = ""

    def __post_init__(self):
        for field in ("candidate_id", "status", "reviewer", "note", "reviewed_at"):
            if not isinstance(getattr(self, field), str):
                raise ValueError(f"{field} must be a string")
        if self.reviewed_at:
            try:
                datetime.fromisoformat(self.reviewed_at.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("reviewed_at must be an ISO timestamp") from None
        if self.status not in {"accepted", "rejected", "unresolved"}:
            raise ValueError("status must be accepted, rejected, or unresolved")
        if self.status != "unresolved" and not self.reviewer.strip():
            raise ValueError("accepted/rejected decisions need a reviewer")


@dataclass(frozen=True)
class Review:
    run_id: str
    decisions: tuple[Decision, ...]

    @classmethod
    def create(cls, result: Reconciliation):
        return cls(result.run_id, tuple(Decision(c.candidate_id) for c in result.candidates))

    def validate(self, result: Reconciliation):
        ids = [d.candidate_id for d in self.decisions]
        if (
            self.run_id != result.run_id
            or len(ids) != len(set(ids))
            or set(ids) != {c.candidate_id for c in result.candidates}
        ):
            raise ValueError("review belongs to a different run or has missing/duplicate/unknown candidates")

    def decide(self, candidate_id, status, *, reviewer, note=""):
        if candidate_id not in {d.candidate_id for d in self.decisions}:
            raise ValueError("unknown candidate ID")
        updated = Decision(candidate_id, status, reviewer, note, datetime.now(timezone.utc).isoformat())
        return replace(
            self, decisions=tuple(updated if d.candidate_id == candidate_id else d for d in self.decisions)
        )
