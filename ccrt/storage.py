"""Versioned JSON bundles and atomic writes for reproducible analysis."""

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from ccrt._version import __version__
from ccrt.merge import MatchConfig, reconcile
from ccrt.review import Decision, Review
from ccrt.schema import SCHEMA_VERSION, Dataset, SourceRecord, ValidationIssue, canonical_json


def atomic_write(path, content, *, overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"output exists: {path}")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if overwrite:
            os.replace(temporary, path)
        else:
            # A hard link fails atomically if another writer created the destination.
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def dataset_dict(dataset):
    return {
        "schema_version": SCHEMA_VERSION,
        "ccrt_version": __version__,
        "kind": "dataset",
        "source": dataset.source,
        "version": dataset.version,
        "input_sha256": dataset.input_sha256,
        "fingerprint": dataset.fingerprint,
        "origin": dataset.origin,
        "metadata_json": dataset.metadata_json,
        "issues": [asdict(i) for i in dataset.issues],
        "records": [r.to_dict() for r in dataset.records],
    }


def _check(payload, kind):
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("kind") != kind
    ):
        raise ValueError(f"unsupported CCRT {kind} bundle/schema version")


def dataset_from_dict(payload):
    _check(payload, "dataset")
    try:
        dataset = Dataset(
            payload["source"],
            payload["version"],
            tuple(SourceRecord.from_dict(r) for r in payload["records"]),
            payload["input_sha256"],
            payload["origin"],
            tuple(ValidationIssue(**i) for i in payload["issues"]),
            payload["metadata_json"],
        )
        if dataset.fingerprint != payload["fingerprint"]:
            raise ValueError("dataset fingerprint mismatch")
        return dataset
    except (KeyError, TypeError) as exc:
        raise ValueError("malformed dataset bundle") from exc


def save_dataset(dataset, path, *, overwrite=False):
    atomic_write(path, canonical_json(dataset_dict(dataset)) + "\n", overwrite=overwrite)


def load_dataset(path):
    return dataset_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_run(result, path, *, overwrite=False):
    payload = {
        "kind": "run",
        "schema_version": SCHEMA_VERSION,
        "ccrt_version": __version__,
        "run_id": result.run_id,
        "algorithm": "interval-haversine-v1",
        "left": dataset_dict(result.left),
        "right": dataset_dict(result.right),
        "config": result.config.to_dict(),
        "candidate_ids": [c.candidate_id for c in result.candidates],
    }
    atomic_write(path, canonical_json(payload) + "\n", overwrite=overwrite)


def load_run(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    _check(payload, "run")
    try:
        if payload["algorithm"] != "interval-haversine-v1":
            raise ValueError("unsupported matching algorithm")
        result = reconcile(
            dataset_from_dict(payload["left"]),
            dataset_from_dict(payload["right"]),
            config=MatchConfig(**payload["config"]),
        )
        if (
            result.run_id != payload["run_id"]
            or [c.candidate_id for c in result.candidates] != payload["candidate_ids"]
        ):
            raise ValueError("run fingerprint/candidates differ; regenerate the run")
        return result
    except (KeyError, TypeError) as exc:
        raise ValueError("malformed run bundle") from exc


def save_review(review, result, path, *, overwrite=False):
    review.validate(result)
    payload = {
        "kind": "review",
        "schema_version": SCHEMA_VERSION,
        "ccrt_version": __version__,
        "run_id": review.run_id,
        "decisions": [asdict(d) for d in review.decisions],
    }
    atomic_write(path, canonical_json(payload) + "\n", overwrite=overwrite)


def load_review(path, result):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    _check(payload, "review")
    try:
        review = Review(payload["run_id"], tuple(Decision(**d) for d in payload["decisions"]))
    except (KeyError, TypeError) as exc:
        raise ValueError("malformed review bundle") from exc
    review.validate(result)
    return review


def atomic_write_bytes(path, content, *, overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"output exists: {path}")
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
