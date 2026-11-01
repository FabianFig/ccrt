# Validation status and practical limits

## Software verification

The offline suite covers source mappings, malformed rows, duplicate IDs, missing
values, precision handling, retry/auth/paging failures, stale reviews, saved bundle
integrity, CLI behavior, and JSON/Parquet round trips. A randomized small comparison
checks the temporal index against an exhaustive pair search. Tests require no API key.

The notebook is executed separately as an end-to-end teaching example. CI targets
Python 3.10–3.14, with Windows and macOS coverage on 3.14. Local verification was
performed on Linux/Python 3.14; remote CI outcomes are not claimed here.

### Installed distribution check

On 2026-09-28, the `0.1.0rc1` wheel and source archive were rebuilt with isolated
build dependencies and passed `twine check`. A fresh Linux/Python 3.14 environment,
outside the checkout, installed the wheel and ran
`benchmarks/smoke_install.py`. The console entry point completed synthetic imports,
matching, review, reporting, and CSV exports. The core environment contained
neither pandas nor PyArrow; imports resolved to the installed package.

After installing the `tables` extra, the same workflow plus a Parquet round trip
and pandas conversion passed, using pandas 3.0.6 and PyArrow 25.0.1. `pip check`
found no broken requirements in either mode. The offline suite had 75 passing
tests, and lint/format checks passed. The package CI job now repeats this installed
workflow in core and tables modes; remote results remain to be checked after push.

Archive inspection confirmed the dashboard and report modules were included,
and excluded `.env`, `.venv`, and `work` paths. A limited scan of the two existing
remote commits, publishable checkout files, and distribution contents found no
copy of the locally configured UCDP key or matches for the credential patterns
checked. This is a recorded check, not a guarantee that every possible secret
format has been detected.

## Synthetic sensitivity study

The four UCDP-shaped and five ACLED-shaped invented records in `examples/` have
three known positive links. Every other pair in that bounded universe is negative.
One positive link has coarse locations, one has an inferred weekly date interval,
and a nearby distinct incident competes with a true link.

| Window | Coarse locations | True links retrieved | False links | Missed true links | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| 0 days / 1 km | excluded | 1 | 1 | 2 | 0.50 | 0.33 |
| 3 days / 25 km | excluded | 2 | 1 | 1 | 0.67 | 0.67 |
| 3 days / 25 km | included | 3 | 1 | 0 | 0.75 | 1.00 |

These are teaching results, **not an estimate of real-world matching quality**.
Even the tightest window includes a false link. Scores cannot establish whether
actors, event units, attribution, or underlying reporting refer to the same event.

Reproduce after the README imports:

```bash
python benchmarks/evaluate.py work/ucdp.json work/acled.json examples/truth_synthetic.csv --exhaustive
```

## Performance baseline

On 2026-09-24, Linux/Python 3.14.7, `python benchmarks/benchmark.py --records 10000`
processed 10,000 records per source and returned 10,000 links in **2.531 seconds**.
The traced peak Python allocation during matching was **12.74 MiB**; this excludes
input construction, interpreter overhead, and native-library allocations. Timing
includes tracing overhead and content fingerprint generation.

The benchmark distributes records over 3,650 dates with deterministic coordinates
and a 1-day/5-km window. It is a reproducible baseline, not a universal capacity
claim. The matcher uses sorted interval starts and prefix maximum ends to skip
impossible dates. Long overlapping intervals or dense same-day data can approach
quadratic work, and retaining every candidate can require quadratic memory. Source
loading and JSON/Parquet exports are currently in memory. Restrict country/date
windows and inspect candidate counts before processing a worldwide archive.

## Prior source-import checks and future linkage validation

On 2026-09-25 UTC, a live authenticated UCDP GED 26.1 query for country 645 and `date_end` between
2020-01-01 and 2020-12-31 retrieved 282 records. The bundle reloaded with its
fingerprint intact and contained no API token. Ten records had out-of-order
low/best/high total fatality estimates; CCRT preserved the values with warnings.
The query used `pagesize=1000` and its canonical result SHA-256 was
`2cde7f13d748efc15faef6ce0f97f0ed7838885665a1609bc5edb0bb20b5c49b`.
The live endpoint used page 0 as its first page, despite documentation examples
using page 1.

A locally supplied ACLED export labeled `export-2026-09-24` contained 48,255 events
from several countries. Filtering by country Iraq and the original reported year
2020 retained 6,306 records, with no import issues. The original file SHA-256 was
`9e1edcba2081f9c42c6dcd0ec652dea4e2245457a1bb591b7229fd8a63aeac2a`;
the bundle preserves this hash and the filter metadata. The reported year filter
retains records whose inferred date intervals extend into an adjacent year.

The default 3-day/25-km run produced 1,329 candidate pairs involving 170 UCDP and
874 ACLED records. Coarse-location exclusions affected 105 UCDP and 285 ACLED
records. Those are software observations, not estimates of matching quality.
Partial manual decisions are local working annotations, not exhaustive reference labels.
`ccrt report` can summarize them without calculating precision or recall.

These checks support the input mappings, but they do not measure real-data matching
quality. The first public `0.1.0` may be released as an experimental library with
this limitation stated plainly. Before making empirical linkage-performance claims:

1. Retain the source snapshots, access permissions, codebook versions, filters, and hashes.
2. Define one country/date sample with compatible scope, including nearby negatives,
   imprecise dates/locations, and source aggregation differences.
3. Review potential links independently of the current candidate thresholds. Record
   all true source-ID pairs within that bounded sample, including links the matcher misses.
4. Run the evaluation script only when labels are exhaustive for those inputs.
5. Report false positives, false negatives, exclusions, threshold sensitivity, and
   sample-selection limitations; retain the labeled evidence for reproducibility.

Partially reviewed candidates alone cannot measure recall: missed true pairs would
never enter the evaluation. Nor do differences in source totals, by themselves,
establish under-reporting or confirm a lower bound on actual harm.
