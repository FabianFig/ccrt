"""Reproducible synthetic throughput baseline. Run after installing CCRT."""

import argparse
import json
import platform
import time
import tracemalloc
from datetime import date, timedelta

from ccrt import Dataset, MatchConfig, SourceRecord, reconcile
from ccrt.schema import digest


def run(count):
    start = date(2000, 1, 1)
    datasets = []
    for source in ("left", "right"):
        records = tuple(
            SourceRecord(
                source,
                str(i),
                "synthetic-v1",
                start + timedelta(days=i % 3650),
                start + timedelta(days=i % 3650),
                latitude=(i % 90) - 45,
                longitude=(i % 180) - 90,
                country="Exampleland",
                date_precision=1,
                geo_precision=1,
            )
            for i in range(count)
        )
        datasets.append(Dataset(source, "synthetic-v1", records, digest([r.to_dict() for r in records])))
    tracemalloc.start()
    began = time.perf_counter()
    result = reconcile(*datasets, config=MatchConfig(max_days=1, max_km=5))
    elapsed = time.perf_counter() - began
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "records_per_source": count,
        "candidates": len(result.candidates),
        "elapsed_seconds": round(elapsed, 3),
        "peak_python_mib": round(peak / 1024**2, 2),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "distribution": "3650 dates, repeated deterministic coordinates; max_days=1, max_km=5",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.records <= 100000:
        parser.error("--records must be between 1 and 100000")
    print(json.dumps(run(args.records), indent=2))
