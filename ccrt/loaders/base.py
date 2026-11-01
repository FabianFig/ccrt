"""Shared validation and CSV mechanics for explicit source adapters."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime
from pathlib import Path

from ccrt.schema import Dataset, SourceRecord, ValidationIssue, canonical_json


class ValidationError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        first = self.issues[0]
        super().__init__(f"{len(self.issues)} invalid row(s); row {first.row}: {first.message}")


def text(value) -> str:
    return "" if value is None else str(value).strip()


def integer(value) -> int | None:
    if value is None or text(value) == "":
        return None
    if isinstance(value, bool) or not re.fullmatch(r"-?\d+", text(value)):
        raise ValueError("expected an integer")
    return int(value)


def number(value) -> float | None:
    return None if value is None or text(value) == "" else float(value)


def parse_date(value) -> date | None:
    value = text(value)
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    # UCDP CSV exports can contain an ISO timestamp; reject ambiguous locale dates.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    raise ValueError("expected an ISO date (YYYY-MM-DD) or ISO timestamp")


def read_csv_rows(path, required):
    payload = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate CSV column names")
    missing = set(required) - set(fields)
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"row {reader.line_num}: CSV field count does not match header")
        rows.append((reader.line_num, row))
    return rows, hashlib.sha256(payload).hexdigest()


def normalize(rows, *, source, version, mapper, input_sha256, origin="", errors="raise", metadata=None):
    if errors not in {"raise", "collect"}:
        raise ValueError("errors must be 'raise' or 'collect'")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("an explicit source version or export snapshot label is required")
    records, issues, seen = [], [], set()
    for line, row in rows:
        raw = canonical_json(row)
        try:
            record = mapper(row, version)
            if record.key in seen:
                raise ValueError(f"duplicate source ID: {record.source_id}")
            seen.add(record.key)
            records.append(record)
            estimates = [
                value
                for value in (record.total_deaths_low, record.total_deaths_best, record.total_deaths_high)
                if value is not None
            ]
            if len(estimates) > 1 and estimates != sorted(estimates):
                issues.append(
                    ValidationIssue(
                        line,
                        "source total death estimates are not ordered low <= best <= high; preserved as reported",
                        "warning",
                        raw,
                    )
                )
            if record.date_start is None or record.latitude is None or record.longitude is None:
                issues.append(
                    ValidationIssue(
                        line, "missing date or coordinate; retained but cannot match", "warning", raw
                    )
                )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            issues.append(ValidationIssue(line, str(exc), "error", raw))
    failures = [i for i in issues if i.severity == "error"]
    if failures and errors == "raise":
        raise ValidationError(failures)
    return Dataset(
        source, version, tuple(records), input_sha256, origin, tuple(issues), canonical_json(metadata or {})
    )


def load_csv(path, source, *, version="user-supplied", errors="raise") -> Dataset:
    """Import the original minimal CSV format; casualty bounds mean TOTAL deaths."""
    rows, sha = read_csv_rows(path, {"source_id", "date", "latitude", "longitude"})

    def mapper(row, version):
        day = parse_date(row["date"])
        low = integer(row.get("fatalities_min"))
        high = integer(row.get("fatalities_max"))
        if low is not None and high is not None and low > high:
            raise ValueError("fatalities_min cannot exceed fatalities_max")
        return SourceRecord(
            source,
            text(row["source_id"]),
            version,
            day,
            day,
            number(row["latitude"]),
            number(row["longitude"]),
            text(row.get("country")),
            total_deaths_low=low,
            total_deaths_high=high,
            raw_json=canonical_json(row),
        )

    return normalize(
        rows,
        source=source,
        version=version,
        mapper=mapper,
        input_sha256=sha,
        origin=Path(path).name,
        errors=errors,
        metadata={"adapter": "generic-v1"},
    )
