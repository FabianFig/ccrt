"""Research tables with original claims and explicit review state."""

import csv
import io
import json
from dataclasses import asdict
from pathlib import Path

from ccrt.review import Review
from ccrt.schema import SourceRecord, canonical_json
from ccrt.storage import atomic_write, dataset_dict, dataset_from_dict


def write_records_csv(dataset, path, *, overwrite=False):
    """Flat normalized table; JSON bundle is the lossless interchange format."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(SourceRecord.__dataclass_fields__))
    writer.writeheader()
    writer.writerows(r.to_dict() for r in dataset)
    atomic_write(path, stream.getvalue(), overwrite=overwrite)


def write_parquet(dataset, path, *, overwrite=False):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise ImportError('Install Parquet support with: pip install "ccrt[tables]"') from None
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"output exists: {path}")
    integers = {
        "date_precision",
        "geo_precision",
        "total_deaths_low",
        "total_deaths_best",
        "total_deaths_high",
        "civilian_deaths",
    }
    fields = [
        (
            name,
            pa.int64()
            if name in integers
            else pa.float64()
            if name in {"latitude", "longitude"}
            else pa.string(),
        )
        for name in SourceRecord.__dataclass_fields__
    ]
    metadata = dataset_dict(dataset)
    metadata.pop("records")
    schema = pa.schema(fields, metadata={b"ccrt": canonical_json(metadata).encode("utf-8")})
    table = pa.Table.from_pylist([r.to_dict() for r in dataset], schema=schema)
    # Serialize before touching the target; null-only and empty columns keep fixed types.
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    from ccrt.storage import atomic_write_bytes

    atomic_write_bytes(path, sink.getvalue().to_pybytes(), overwrite=overwrite)


def read_parquet(path):
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise ImportError('Install Parquet support with: pip install "ccrt[tables]"') from None
    table = pq.read_table(path)
    if b"ccrt" not in (table.schema.metadata or {}):
        raise ValueError("Parquet file has no CCRT provenance; import it through a source adapter")
    payload = json.loads(table.schema.metadata[b"ccrt"])
    payload["records"] = table.to_pylist()
    return dataset_from_dict(payload)


def write_csv(result, path, *, review=None, overwrite=False):
    """Write candidates and unlinked accounts. Several rows may refer to one record."""
    review = review or Review.create(result)
    review.validate(result)
    decisions = {d.candidate_id: d for d in review.decisions}
    evidence = [
        "candidate_id",
        "status",
        "reviewer",
        "note",
        "reviewed_at",
        "run_id",
        "days_apart",
        "distance_km",
        "match_score",
        "warnings",
        "unlinked_reason",
    ]
    columns = list(SourceRecord.__dataclass_fields__)
    fields = evidence + [f"{side}_{field}" for side in ("left", "right") for field in columns]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    run_id = result.run_id
    for candidate in result.candidates:
        writer.writerow(
            {
                **asdict(decisions[candidate.candidate_id]),
                "run_id": run_id,
                "days_apart": candidate.days_apart,
                "distance_km": round(candidate.distance_km, 3),
                "match_score": round(candidate.score, 6),
                "warnings": ";".join(candidate.warnings),
                **{f"left_{k}": v for k, v in candidate.left.to_dict().items()},
                **{f"right_{k}": v for k, v in candidate.right.to_dict().items()},
            }
        )
    for item in result.unlinked:
        side = "left" if item.record.source == result.left.source else "right"
        writer.writerow(
            {
                "status": "unlinked",
                "run_id": run_id,
                "unlinked_reason": item.reason,
                **{f"{side}_{k}": v for k, v in item.record.to_dict().items()},
            }
        )
    atomic_write(path, stream.getvalue(), overwrite=overwrite)


def read_review_csv(path, result):
    """Read only review fields from a previously exported candidate CSV."""
    from datetime import datetime, timezone

    from ccrt.review import Decision

    decisions = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"candidate_id", "status", "reviewer", "note", "reviewed_at", "run_id"}
        if not required <= set(reader.fieldnames or ()):
            raise ValueError("review CSV is missing review columns")
        for row in reader:
            if row["run_id"] != result.run_id:
                raise ValueError(f"review CSV line {reader.line_num}: belongs to a different run")
            if row["status"] == "unlinked" and not row["candidate_id"]:
                continue
            if row["status"] != "unresolved" and not row["reviewed_at"]:
                row["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            try:
                decisions.append(Decision(**{k: row[k] for k in required if k != "run_id"}))
            except ValueError as exc:
                pair = f"{row.get('left_source_id', '?')}/{row.get('right_source_id', '?')}"
                raise ValueError(f"review CSV line {reader.line_num} ({pair}): {exc}") from exc
    review = Review(result.run_id, tuple(decisions))
    review.validate(result)
    return review
