"""Source accounts and provenance; linking accounts never changes these records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from functools import cached_property
from math import isfinite

SCHEMA_VERSION = 1


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceRecord:
    source: str
    source_id: str
    version: str
    date_start: date | None
    date_end: date | None
    latitude: float | None = None
    longitude: float | None = None
    country: str = ""
    date_precision: int | None = None
    geo_precision: int | None = None
    date_basis: str = "reported"
    actor1: str = ""
    actor2: str = ""
    event_type: str = ""
    total_deaths_low: int | None = None
    total_deaths_best: int | None = None
    total_deaths_high: int | None = None
    civilian_deaths: int | None = None
    raw_json: str = "{}"

    def __post_init__(self) -> None:
        for field in ("source", "source_id", "version"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a nonempty string")
        for field in ("date_start", "date_end"):
            value = getattr(self, field)
            if value is not None and type(value) is not date:
                raise ValueError(f"{field} must be a date or None")
        if (self.date_start is None) != (self.date_end is None):
            raise ValueError("both date bounds must be present or missing")
        if self.date_start is not None and self.date_start > self.date_end:
            raise ValueError("date_start exceeds date_end")
        for field, limit in (("latitude", 90), ("longitude", 180)):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or not -limit <= value <= limit
            ):
                raise ValueError(f"{field} must be finite and within ±{limit}")
        for field in ("total_deaths_low", "total_deaths_best", "total_deaths_high", "civilian_deaths"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{field} must be a nonnegative integer or None")
        for field in ("date_precision", "geo_precision"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"{field} must be a positive integer or None")
        if not isinstance(json.loads(self.raw_json), dict):
            raise ValueError("raw_json must encode an object")

    @property
    def key(self) -> str:
        return canonical_json([self.source, self.version, self.source_id])

    @property
    def raw(self) -> dict:
        """Return a fresh copy so callers cannot mutate stored provenance."""
        return json.loads(self.raw_json)

    def to_dict(self) -> dict:
        result = asdict(self)
        for field in ("date_start", "date_end"):
            result[field] = getattr(self, field).isoformat() if getattr(self, field) else None
        return result

    @classmethod
    def from_dict(cls, value: dict) -> SourceRecord:
        values = dict(value)
        for field in ("date_start", "date_end"):
            values[field] = date.fromisoformat(values[field]) if values[field] else None
        return cls(**values)


@dataclass(frozen=True)
class ValidationIssue:
    row: int
    message: str
    severity: str = "error"
    raw_json: str = "{}"


@dataclass(frozen=True)
class Dataset:
    source: str
    version: str
    records: tuple[SourceRecord, ...]
    input_sha256: str
    origin: str = ""
    issues: tuple[ValidationIssue, ...] = ()
    metadata_json: str = "{}"

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "issues", tuple(self.issues))
        if not self.source.strip() or not self.version.strip():
            raise ValueError("dataset source and version are required")
        keys = set()
        for record in self.records:
            if record.source != self.source or record.version != self.version:
                raise ValueError("record source/version differs from dataset")
            if record.key in keys:
                raise ValueError(f"duplicate record ID: {record.source_id}")
            keys.add(record.key)
        if not isinstance(json.loads(self.metadata_json), dict):
            raise ValueError("metadata_json must encode an object")

    @cached_property
    def fingerprint(self) -> str:
        """Content identity includes normalized records, mapping metadata and rejected rows."""
        return digest(
            {
                "source": self.source,
                "version": self.version,
                "input_sha256": self.input_sha256,
                "metadata": json.loads(self.metadata_json),
                "issues": [asdict(i) for i in self.issues],
                "records": sorted((r.to_dict() for r in self.records), key=lambda r: r["source_id"]),
            }
        )

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def to_pandas(self):
        """Return flat columns with nullable types. Requires the tables extra."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError('Install table support with: pip install "ccrt[tables]"') from None
        return pd.DataFrame(
            [r.to_dict() for r in self.records], columns=SourceRecord.__dataclass_fields__
        ).convert_dtypes()
