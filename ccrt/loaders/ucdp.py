"""UCDP GED 25.1/26.1 field mapping. Other versions require independent validation."""

from pathlib import Path

from ccrt.loaders.base import integer, normalize, number, parse_date, read_csv_rows, text
from ccrt.schema import SourceRecord, canonical_json, digest

REQUIRED = {"id", "date_start", "date_end", "latitude", "longitude", "country"}
SUPPORTED_VERSIONS = {"25.1", "26.1"}


def check_version(version):
    if version not in SUPPORTED_VERSIONS:
        raise ValueError("supported UCDP GED versions: 25.1, 26.1")


def map_record(row, version):
    missing = REQUIRED - row.keys()
    if missing:
        raise ValueError(f"missing UCDP fields: {', '.join(sorted(missing))}")
    date_precision = integer(row.get("date_prec"))
    geo_precision = integer(row.get("where_prec"))
    if date_precision is not None and date_precision not in range(1, 6):
        raise ValueError("UCDP date_prec must be 1 through 5")
    if geo_precision is not None and geo_precision not in range(1, 8):
        raise ValueError("UCDP where_prec must be 1 through 7")
    return SourceRecord(
        source="ucdp",
        source_id=text(row["id"]),
        version=version,
        date_start=parse_date(row["date_start"]),
        date_end=parse_date(row["date_end"]),
        latitude=number(row["latitude"]),
        longitude=number(row["longitude"]),
        country=text(row["country"]),
        date_precision=date_precision,
        geo_precision=geo_precision,
        actor1=text(row.get("side_a")),
        actor2=text(row.get("side_b")),
        event_type=text(row.get("type_of_violence")),
        total_deaths_low=integer(row.get("low")),
        total_deaths_best=integer(row.get("best")),
        total_deaths_high=integer(row.get("high")),
        civilian_deaths=integer(row.get("deaths_civilians")),
        raw_json=canonical_json(row),
    )


def load_ucdp_csv(path, *, version, errors="raise"):
    check_version(version)
    rows, sha = read_csv_rows(path, REQUIRED)
    return normalize(
        rows,
        source="ucdp",
        version=version,
        mapper=map_record,
        input_sha256=sha,
        origin=Path(path).name,
        errors=errors,
        metadata={"adapter": "ucdp-ged-v1"},
    )


def from_api_records(records, *, version, metadata=None, errors="raise"):
    check_version(version)
    return normalize(
        enumerate(records, 1),
        source="ucdp",
        version=version,
        mapper=map_record,
        input_sha256=digest(records),
        origin="ucdp-api",
        errors=errors,
        metadata={"adapter": "ucdp-ged-v1", **(metadata or {})},
    )
