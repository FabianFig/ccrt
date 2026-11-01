"""Inspectable candidate generation. No automatic assignment or casualty aggregation."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from functools import cached_property
from math import asin, cos, isfinite, radians, sin, sqrt
from types import MappingProxyType

from ccrt.schema import Dataset, SourceRecord, digest


@dataclass(frozen=True)
class MatchConfig:
    max_days: int = 3
    max_km: float = 25.0
    include_coarse_locations: bool = False
    country_aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if type(self.max_days) is not int or self.max_days < 0:
            raise ValueError("max_days must be a nonnegative integer")
        if (
            isinstance(self.max_km, bool)
            or not isinstance(self.max_km, (int, float))
            or not isfinite(self.max_km)
            or self.max_km <= 0
        ):
            raise ValueError("max_km must be finite and positive")
        if type(self.include_coarse_locations) is not bool:
            raise ValueError("include_coarse_locations must be boolean")
        if any(
            not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip()
            for k, v in self.country_aliases.items()
        ):
            raise ValueError("country_aliases must map nonempty strings to nonempty strings")
        object.__setattr__(
            self,
            "country_aliases",
            MappingProxyType(
                {k.strip().casefold(): v.strip().casefold() for k, v in self.country_aliases.items()}
            ),
        )

    def to_dict(self):
        return {
            "max_days": self.max_days,
            "max_km": self.max_km,
            "include_coarse_locations": self.include_coarse_locations,
            "country_aliases": dict(self.country_aliases),
        }


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    left: SourceRecord
    right: SourceRecord
    days_apart: int
    distance_km: float
    score: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnlinkedRecord:
    record: SourceRecord
    reason: str


@dataclass(frozen=True)
class Reconciliation:
    left: Dataset
    right: Dataset
    config: MatchConfig
    candidates: tuple[Candidate, ...]
    unlinked: tuple[UnlinkedRecord, ...]

    @cached_property
    def run_id(self):
        return digest(
            {
                "left": self.left.fingerprint,
                "right": self.right.fingerprint,
                "config": self.config.to_dict(),
                "algorithm": "interval-haversine-v1",
            }
        )


def distance_km(left: SourceRecord, right: SourceRecord) -> float:
    if any(v is None for v in (left.latitude, left.longitude, right.latitude, right.longitude)):
        raise ValueError("distance needs complete coordinates")
    lat1, lat2 = radians(left.latitude), radians(right.latitude)
    a = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(radians(right.longitude - left.longitude) / 2) ** 2
    )
    return 6371.0088 * 2 * asin(min(1.0, sqrt(max(0.0, a))))


def _ineligible(record, config):
    if record.date_start is None:
        return "missing_date"
    if record.latitude is None or record.longitude is None:
        return "missing_coordinates"
    if (
        not config.include_coarse_locations
        and record.source in {"ucdp", "acled"}
        and record.geo_precision is not None
        and record.geo_precision >= 3
    ):
        return "coarse_location_excluded"
    return None


def _country(record, config):
    country = record.country.strip().casefold()
    return config.country_aliases.get(country, country)


def reconcile(left: Dataset, right: Dataset, *, config: MatchConfig | None = None) -> Reconciliation:
    """Return all eligible pairs; a record may occur in several candidates.

    Date distance is the gap between closed intervals. Location precision codes are
    source-specific categories, not radii. Coarse locations are excluded by default.
    """
    config = config or MatchConfig()
    if left.source == right.source:
        raise ValueError("reconciliation requires distinct sources")
    seed = digest(
        {
            "left": left.fingerprint,
            "right": right.fingerprint,
            "config": config.to_dict(),
            "algorithm": "interval-haversine-v1",
        }
    )
    eligible_right = sorted(
        (r for r in right if not _ineligible(r, config)), key=lambda r: (r.date_start, r.key)
    )
    starts = [r.date_start.toordinal() for r in eligible_right]
    prefix_ends = []
    for record in eligible_right:
        prefix_ends.append(max(record.date_end.toordinal(), prefix_ends[-1] if prefix_ends else 0))
    candidates, linked = [], set()
    for a in sorted(left, key=lambda r: r.key):
        if _ineligible(a, config):
            continue
        lower = a.date_start.toordinal() - config.max_days
        upper = a.date_end.toordinal() + config.max_days
        begin = bisect_left(prefix_ends, lower)
        end = bisect_right(starts, upper)
        for index in range(begin, end):
            b = eligible_right[index]
            if b.date_end.toordinal() < lower:
                continue
            ca, cb = _country(a, config), _country(b, config)
            if ca and cb and ca != cb:
                continue
            gap = max(0, (a.date_start - b.date_end).days, (b.date_start - a.date_end).days)
            km = distance_km(a, b)
            if km > config.max_km:
                continue
            warnings = []
            if not ca or not cb:
                warnings.append("country_missing")
            for side, record in (("left", a), ("right", b)):
                if record.date_start != record.date_end or record.date_precision != 1:
                    warnings.append(f"{side}_date_uncertain")
                if record.geo_precision != 1:
                    warnings.append(f"{side}_location_uncertain")
                if record.date_basis != "reported":
                    warnings.append(f"{side}_date_interval_inferred")
            score = 1 - (gap / (config.max_days + 1) + km / config.max_km) / 2
            identifier = digest([seed, a.key, b.key])
            candidates.append(Candidate(identifier, a, b, gap, km, score, tuple(warnings)))
            linked.update((a.key, b.key))
    candidates.sort(key=lambda c: (-c.score, c.left.key, c.right.key))
    unlinked = tuple(
        UnlinkedRecord(r, _ineligible(r, config) or "no_candidate")
        for r in sorted((*left.records, *right.records), key=lambda r: r.key)
        if r.key not in linked
    )
    return Reconciliation(left, right, config, tuple(candidates), unlinked)
