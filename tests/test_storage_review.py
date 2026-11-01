import csv
import json
from dataclasses import replace

import pytest

from ccrt import MatchConfig, Review, reconcile
from ccrt.export import read_parquet, read_review_csv, write_csv, write_parquet
from ccrt.storage import load_dataset, load_review, load_run, save_dataset, save_review, save_run


def test_json_roundtrip_and_tamper_detection(source_pair, tmp_path):
    path = tmp_path / "dataset.json"
    save_dataset(source_pair[0], path)
    restored = load_dataset(path)
    assert restored == source_pair[0]
    payload = json.loads(path.read_text())
    payload["records"][0]["total_deaths_best"] = 5
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        load_dataset(path)


def test_unknown_schema_rejected(source_pair, tmp_path):
    path = tmp_path / "dataset.json"
    save_dataset(source_pair[0], path)
    payload = json.loads(path.read_text())
    payload["schema_version"] = 999
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="schema version"):
        load_dataset(path)


def test_run_review_roundtrip_and_stale_review(source_pair, tmp_path):
    result = reconcile(*source_pair)
    run_path = tmp_path / "run.json"
    save_run(result, run_path)
    assert load_run(run_path) == result
    review = Review.create(result).decide(
        result.candidates[0].candidate_id, "accepted", reviewer="Fabian", note="Compared accounts"
    )
    path = tmp_path / "review.json"
    save_review(review, result, path)
    assert load_review(path, result) == review
    changed = reconcile(*source_pair, config=MatchConfig(max_days=0))
    with pytest.raises(ValueError, match="different run"):
        load_review(path, changed)
    assert all(d.status == "unresolved" for d in Review.create(result).decisions)


def test_review_requires_reviewer_and_known_id(source_pair):
    result = reconcile(*source_pair)
    review = Review.create(result)
    with pytest.raises(ValueError, match="reviewer"):
        review.decide(result.candidates[0].candidate_id, "accepted", reviewer="")
    with pytest.raises(ValueError, match="unknown candidate"):
        review.decide("unknown", "rejected", reviewer="Fabian")
    duplicated = replace(review, decisions=(*review.decisions, review.decisions[0]))
    with pytest.raises(ValueError, match="duplicate"):
        duplicated.validate(result)


def test_review_csv_roundtrip_and_claims(source_pair, tmp_path):
    result = reconcile(*source_pair)
    path = tmp_path / "review.csv"
    write_csv(result, path)
    assert read_review_csv(path, result) == Review.create(result)
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames
    match = next(r for r in rows if r["left_source_id"] == "U1" and r["right_source_id"] == "A1")
    assert match["left_civilian_deaths"] == "1"
    assert match["right_civilian_deaths"] == ""
    assert match["left_total_deaths_best"] == "4"
    assert match["right_total_deaths_best"] == "3"
    match.update(status="rejected", reviewer="Fabian", note="Reviewed narrative")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert any(d.status == "rejected" for d in read_review_csv(path, result).decisions)


def test_review_csv_reports_row_and_pair_when_reviewer_missing(source_pair, tmp_path):
    result = reconcile(*source_pair)
    path = tmp_path / "review.csv"
    write_csv(result, path)
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames
    rows[0]["status"] = "accepted"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(
        ValueError, match=r"review CSV line 2 \(U2/A3\): accepted/rejected decisions need a reviewer"
    ):
        read_review_csv(path, result)


def test_no_overwrite(source_pair, tmp_path):
    path = tmp_path / "data.json"
    save_dataset(source_pair[0], path)
    with pytest.raises(FileExistsError):
        save_dataset(source_pair[1], path)
    assert load_dataset(path) == source_pair[0]


def test_parquet_roundtrip_empty_and_null_columns(source_pair, tmp_path):
    pytest.importorskip("pyarrow")
    for index, data in enumerate([source_pair[0], source_pair[1], replace(source_pair[0], records=())]):
        path = tmp_path / f"{index}.parquet"
        write_parquet(data, path)
        assert read_parquet(path) == data


def test_pandas_nullable_types(source_pair):
    pd = pytest.importorskip("pandas")
    frame = source_pair[1].to_pandas()
    assert frame["total_deaths_best"].dtype == pd.Int64Dtype()
    assert frame["total_deaths_best"].iloc[2] == 0
    assert pd.isna(frame["total_deaths_best"].iloc[4])
