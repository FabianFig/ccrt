from datetime import date
from pathlib import Path

import pytest

from ccrt import Dataset, SourceRecord, load_acled_csv, load_ucdp_csv
from ccrt.schema import digest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def source_pair():
    return (
        load_ucdp_csv(EXAMPLES / "ucdp_synthetic.csv", version="26.1"),
        load_acled_csv(EXAMPLES / "acled_synthetic.csv", version="synthetic-2026-09-24"),
    )


def record(source, source_id="1", start=date(2020, 1, 1), end=None, **kwargs):
    defaults = {
        "latitude": 0.0,
        "longitude": 0.0,
        "country": "Exampleland",
        "date_precision": 1,
        "geo_precision": 1,
    }
    defaults.update(kwargs)
    return SourceRecord(source, source_id, "test", start, end if end is not None else start, **defaults)


def dataset(source, records):
    return Dataset(source, "test", tuple(records), digest([r.to_dict() for r in records]))
