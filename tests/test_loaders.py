import csv
from datetime import date
from io import StringIO

import pytest

from ccrt import ValidationError, load_csv, load_ucdp_csv
from ccrt.loaders.acled import map_record as acled_record
from ccrt.loaders.ucdp import from_api_records, map_record


def ucdp_row(**changes):
    return {
        "id": 1,
        "date_start": "2020-01-01",
        "date_end": "2020-01-02",
        "latitude": 0,
        "longitude": 0,
        "country": "Exampleland",
        "date_prec": 2,
        "where_prec": 1,
        "best": 8,
        "low": 5,
        "high": 10,
        "deaths_civilians": 2,
        "source_article": "example",
        **changes,
    }


def write_source(tmp_path, rows):
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path = tmp_path / "source.csv"
    # csv already writes CRLF; avoid Windows translating it into CRCRLF.
    path.write_bytes(stream.getvalue().encode("utf-8"))
    return path


def test_ucdp_mapping_and_provenance(source_pair):
    left, right = source_pair
    assert left.records[0].total_deaths_best == 4
    assert left.records[0].civilian_deaths == 1
    assert left.records[0].raw["source_article"] == "Synthetic account A"
    assert left.records[0].raw["event_clarity"] == "1"
    assert right.records[0].civilian_deaths is None
    assert right.records[0].total_deaths_best == 3
    assert right.records[2].total_deaths_best == 0
    assert right.records[4].total_deaths_best is None
    assert len(left.issues) == 1
    assert left.issues[0].severity == "warning"
    assert left.records[3].latitude is None


def test_raw_is_defensive_copy():
    original = ucdp_row()
    rec = map_record(original, "26.1")
    original["best"] = 100
    raw = rec.raw
    raw["best"] = 900
    assert rec.raw["best"] == 8


@pytest.mark.parametrize(
    "changes",
    [
        {"latitude": "nan"},
        {"longitude": 181},
        {"best": -1},
        {"best": 1.5},
        {"date_start": "01/02/2020"},
        {"date_end": "2019-01-01"},
        {"date_prec": 6},
        {"where_prec": 8},
    ],
)
def test_bad_ucdp_rows_have_context(tmp_path, changes):
    path = write_source(tmp_path, [ucdp_row(**changes)])
    with pytest.raises(ValidationError) as error:
        load_ucdp_csv(path, version="26.1")
    assert error.value.issues[0].row == 2


def test_csv_and_api_agree(tmp_path):
    row = ucdp_row()
    csv_data = load_ucdp_csv(write_source(tmp_path, [row]), version="26.1")
    api_data = from_api_records([row], version="26.1")
    a, b = csv_data.records[0].to_dict(), api_data.records[0].to_dict()
    a.pop("raw_json")
    b.pop("raw_json")
    assert a == b


def test_source_inconsistent_totals_are_preserved_with_warning(tmp_path):
    row = ucdp_row(low=12)
    data = load_ucdp_csv(write_source(tmp_path, [row]), version="26.1")
    assert len(data) == 1
    assert data.records[0].total_deaths_low == 12
    assert data.records[0].total_deaths_best == 8
    assert len(data.issues) == 1
    assert data.issues[0].severity == "warning"
    assert "not ordered" in data.issues[0].message


def test_collect_invalid_and_duplicate_rows(tmp_path):
    path = write_source(tmp_path, [ucdp_row(), ucdp_row(latitude=200), ucdp_row()])
    data = load_ucdp_csv(path, version="26.1", errors="collect")
    assert len(data) == 1
    assert [i.row for i in data.issues] == [3, 4]
    assert data.issues[0].raw_json
    with pytest.raises(ValidationError):
        load_ucdp_csv(path, version="26.1")


def test_missing_headers_and_duplicate_headers(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("id,id\n1,1\n")
    with pytest.raises(ValueError, match="duplicate CSV"):
        load_ucdp_csv(path, version="26.1")
    path.write_text("id\n1\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_ucdp_csv(path, version="26.1")


def test_empty_csv_and_wrong_field_count(tmp_path):
    path = write_source(tmp_path, [ucdp_row()])
    path.write_text(path.read_text().splitlines()[0] + "\n")
    assert len(load_ucdp_csv(path, version="26.1")) == 0
    path.write_text(path.read_text() + "1,too,few\n")
    with pytest.raises(ValueError, match="field count"):
        load_ucdp_csv(path, version="26.1")


def test_acled_inferred_intervals(source_pair):
    _, right = source_pair
    weekly, monthly = right.records[2:4]
    assert (weekly.date_start, weekly.date_end) == (date(2020, 1, 7), date(2020, 1, 13))
    assert (monthly.date_start, monthly.date_end) == (date(2020, 2, 1), date(2020, 2, 29))
    assert monthly.date_basis == "inferred-month-envelope"
    assert monthly.raw["event_date"] == "2020-02-15"


def test_acled_invalid_precision(source_pair):
    row = source_pair[1].records[0].raw
    row["time_precision"] = "4"
    with pytest.raises(ValueError, match="precision"):
        acled_record(row, "snapshot")


def test_versions_required(tmp_path):
    path = write_source(tmp_path, [ucdp_row()])
    with pytest.raises(ValueError, match="supported UCDP"):
        load_ucdp_csv(path, version="latest")
    with pytest.raises(ValueError, match="snapshot"):
        from ccrt.loaders.base import normalize

        normalize([], source="acled", version="", mapper=acled_record, input_sha256="")


def test_generic_unknown_counts(tmp_path):
    path = tmp_path / "generic.csv"
    path.write_text("source_id,date,latitude,longitude,fatalities_min,fatalities_max\nx,2020-01-01,0,0,,\n")
    data = load_csv(path, "custom")
    assert data.records[0].total_deaths_low is None
    assert data.records[0].latitude == 0


def test_generic_range_still_rejects_reversed_bounds(tmp_path):
    path = tmp_path / "generic.csv"
    path.write_text("source_id,date,latitude,longitude,fatalities_min,fatalities_max\nx,2020-01-01,0,0,5,2\n")
    with pytest.raises(ValidationError, match="fatalities_min cannot exceed fatalities_max"):
        load_csv(path, "custom")
