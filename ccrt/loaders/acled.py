"""ACLED event CSV mapping (current lowercase columns, codebook 2024 onward)."""

import calendar
from datetime import timedelta
from pathlib import Path

from ccrt.loaders.base import integer, normalize, number, parse_date, read_csv_rows, text
from ccrt.schema import SourceRecord, canonical_json

REQUIRED = {
    "event_id_cnty",
    "event_date",
    "time_precision",
    "latitude",
    "longitude",
    "geo_precision",
    "country",
    "fatalities",
}


def map_record(row, version):
    day = parse_date(row["event_date"])
    precision = integer(row["time_precision"])
    geo = integer(row["geo_precision"])
    if precision not in {None, 1, 2, 3} or geo not in {None, 1, 2, 3}:
        raise ValueError("ACLED precision codes must be 1, 2, 3, or blank")
    start = end = day
    basis = "reported"
    if day and precision == 2:
        start, end = day - timedelta(days=3), day + timedelta(days=3)
        basis = "inferred-week-envelope"
    elif day and precision == 3:
        start = day.replace(day=1)
        end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        basis = "inferred-month-envelope"
    return SourceRecord(
        source="acled",
        source_id=text(row["event_id_cnty"]),
        version=version,
        date_start=start,
        date_end=end,
        latitude=number(row["latitude"]),
        longitude=number(row["longitude"]),
        country=text(row["country"]),
        date_precision=precision,
        geo_precision=geo,
        date_basis=basis,
        actor1=text(row.get("actor1")),
        actor2=text(row.get("actor2")),
        event_type=text(row.get("event_type")),
        total_deaths_best=integer(row["fatalities"]),
        raw_json=canonical_json(row),
    )


def load_acled_csv(path, *, version, errors="raise"):
    """version is a user-supplied export snapshot label, not an ACLED release number."""
    rows, sha = read_csv_rows(path, REQUIRED)
    return normalize(
        rows,
        source="acled",
        version=version,
        mapper=map_record,
        input_sha256=sha,
        origin=Path(path).name,
        errors=errors,
        metadata={"adapter": "acled-event-v1", "date_policy": "week ±3 days; month envelope"},
    )
