# Conflict Casualty Reconciliation Toolkit (CCRT)

CCRT compares source accounts of conflict incidents. It imports UCDP GED and ACLED
records, proposes possible links, supports human review, and exports results while
preserving each source's original claims.

**Status:** `0.1.0rc1` is an unpublished package preview. The planned `0.1.0`
release is an experimental research library.

## Installation

CCRT supports Python 3.10–3.14. From a checkout of this repository:

```bash
python -m pip install -e .
```

Install `.[tables]` for pandas and Parquet support, or `.[tables,dev]` for the
project's development checks. CCRT has not yet been published to PyPI.

## Quickstart

The example files contain invented incidents in Exampleland. From the repository
root, with an unused `work/` directory:

```bash
mkdir -p work
ccrt import ucdp examples/ucdp_synthetic.csv work/ucdp.json --version 26.1
ccrt import acled examples/acled_synthetic.csv work/acled.json --version synthetic-2026-09-24
ccrt match work/ucdp.json work/acled.json work/matches
ccrt report work/matches/run.json --review work/matches/review.json
```

The match run contains three candidate links and four unlinked source records.
Inspect `work/matches/candidates.csv`, then use the [usage guide](docs/usage.md) to
record decisions and export reviewed results. CCRT does not overwrite existing
outputs.

## Python API

```python
from ccrt import MatchConfig, load_acled_csv, load_ucdp_csv, reconcile

ucdp = load_ucdp_csv("examples/ucdp_synthetic.csv", version="26.1")
acled = load_acled_csv("examples/acled_synthetic.csv", version="synthetic-2026-09-24")
result = reconcile(ucdp, acled, config=MatchConfig(max_days=3, max_km=25))

for candidate in result.candidates:
    print(candidate.left.source_id, candidate.right.source_id, candidate.score)
```

The [API reference](docs/api.md) covers review decisions, saved runs, reports, and
exports.

## Sources and capabilities

- UCDP GED 25.1 and 26.1 CSV files with modern field names, and authenticated GED
  API access.
- ACLED event CSV exports with current lowercase field names. The supplied version
  is a label for the exact export snapshot.
- Source-preserving JSON bundles, candidate generation, CSV and terminal review,
  review reports, CSV export, and optional Parquet export.

See [source mappings](docs/source-mappings.md) for supported fields, precision
handling, and provenance. The [teaching notebook](examples/reconciliation_walkthrough.ipynb)
provides another offline example.

## Limitations

CCRT compares source accounts; it does not establish objective incident identity.
Candidate scores are uncalibrated proximity rankings, and generating a candidate
does not confirm correspondence. Real-world linkage accuracy has not been
independently evaluated. CCRT does not reconcile casualty totals or estimate
underreporting. See [validation notes](docs/validation.md) for software checks and
research limits.

## Contributing and licence

See [CONTRIBUTING.md](CONTRIBUTING.md), the [changelog](CHANGELOG.md), and the
[release procedure](docs/releasing.md). The code and synthetic examples are under
the [MIT licence](LICENSE). UCDP and ACLED data have separate access, attribution,
and redistribution terms; obtain source access and check the terms for your snapshot.
