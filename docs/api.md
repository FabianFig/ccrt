# Public API (0.1.0)

`0.1.0` is an experimental library release. The API returns
source accounts, candidate links, and review decisions. It does not establish
incident identity or provide measured real-data matching accuracy. Candidate scores
are uncalibrated proximity rankings.

Names exported from `ccrt` are the supported entry points. Modules prefixed with
an underscore and individual loader mapping helpers are implementation details.
Before 1.0, interface changes will be documented in the changelog.
For the CLI workflow, see the [usage guide](usage.md).

## Import and inspect

```python
from ccrt import load_ucdp_csv, load_acled_csv, UCDPClient

ucdp = load_ucdp_csv("ged.csv", version="26.1", errors="raise")
acled = load_acled_csv("acled.csv", version="export-2026-09-24", errors="collect")
for issue in acled.issues:
    print(issue.row, issue.severity, issue.message)

with UCDPClient() as client:  # UCDP_API_KEY; api_key= also supported
    data = client.fetch(
        version="26.1",
        countries=[645],
        start_date="2020-01-01",
        end_date="2020-12-31",
        types_of_violence=[1, 3],
        page_size=1000,
        max_pages=100,
    )
```

All loaders return `Dataset`. It contains immutable record/issue tuples, source,
version, origin, input SHA-256, metadata JSON, and a content fingerprint. Iteration
and `len(dataset)` operate on valid records. `to_pandas()` returns normalised
columns with nullable types; dates are ISO strings and raw accounts are JSON strings.

`SourceRecord` stores a source account, with optional dates/coordinates and separate
total and civilian fatality estimates. `raw` is a defensive copy. Construct custom
records with `SourceRecord(...)` and `Dataset(...)`; use `load_csv` for the original
minimal CSV format. Both date bounds must be present or both missing. Custom source
records should provide an explicit snapshot label and a reproducible input hash.

`UCDPClient(timeout=30, retries=3)` retries transport failures and HTTP 429/500/502/
503/504. Backoff is bounded; Retry-After greater than 30 seconds asks the caller to
try later. It never follows redirects, returns partial datasets, or embeds response
bodies in errors. No credentials are required to import the library or run tests.
The live GED endpoint returned zero-indexed pages in a checked query on
2026-09-24; the client starts at page 0 and verifies the final record count.
The `fetch-ucdp` CLI command also reads `UCDP_API_KEY` from `.env` in its current
directory when the variable is absent; `--env-file PATH` selects another file.
Only that key is read, and process environment variables take precedence.
`ValidationError` exposes `.issues`; `UCDPError` reports sanitised transport/API errors.

## Generate and review

```python
from ccrt import MatchConfig, reconcile, Review

config = MatchConfig(max_days=3, max_km=25, country_aliases={"Yemen (North Yemen)": "Yemen"})
result = reconcile(ucdp, acled, config=config)
review = Review.create(result)
# Choose an ID only after inspecting evidence:
# review = review.decide(candidate_id, 'accepted', reviewer='Name', note='Reason')
```

`Reconciliation` contains both datasets, settings, `candidates`, `unlinked`, and
`run_id`. Each `Candidate` contains its two source accounts, interval gap, distance,
heuristic score, warnings, and ID. `UnlinkedRecord.reason` distinguishes missing
dates, missing coordinates, coarse exclusions, and absence of an eligible pair.
`Review.decide` returns a new review. It never modifies source accounts. Many-to-many
accepted links are allowed; consolidation is outside this API.

For manual work, `ccrt review-interactive RUN.json SESSION.json --reviewer NAME`
shows one left-side record alongside its candidate accounts and saves each decision
to `SESSION.json`. Add `--from-existing REVIEW.json` only when first creating the
session. Re-run without that option to resume. `--left-id ID` starts at one source
record and continues through the queue; `--all` includes groups whose candidates
are already decided.

`ccrt review-tui RUN.json SESSION.json --reviewer NAME` is an experimental
full-screen alternative for an interactive terminal. It writes the same review
JSON format and accepts `--from-existing` when creating a session or `--left-id`
to start at a particular source record.

`summarize_review(result, review=None)` returns a `ReviewReport`; an omitted review
treats all candidates as unresolved. The report counts unique source records,
reviewed/accepted/rejected/unresolved candidates, and unlinked reasons. It lists
accepted records with multiple counterparts, accepted pairs with different reported
fatalities, and accepted pairs with missing fatality values. Missing values are
kept separate from reported zero. The report does not aggregate fatalities.

```python
from ccrt import summarize_review

report = summarize_review(result, review)
print(report.reviewed_count, report.candidate_count)
payload = report.to_dict()
```

`reviewed_fraction` is `None` for an empty candidate set. Score bounds are `None`
when no candidate has been accepted or rejected. `to_dict()` includes the run ID,
library version, and a fingerprint of the review decisions; no raw accounts are
included. Reports reject reviews bound to another run. The CLI equivalent is
`ccrt report RUN.json --review REVIEW.json [--output REPORT.json]`.

Candidate IDs bind to the full datasets and settings. Updating inputs or settings
requires generating and reviewing a new run. Input row order does not affect
candidate ordering, provided source fingerprints/metadata remain the same.

## Save and export

```python
from ccrt import save_dataset, load_dataset, save_run, load_run, save_review, load_review
from ccrt.export import write_records_csv, write_csv, read_review_csv, write_parquet, read_parquet

save_dataset(ucdp, "ucdp.json")
save_run(result, "run.json")
save_review(review, result, "review.json")
write_csv(result, "review.csv", review=review)
write_records_csv(ucdp, "records.csv")
write_parquet(ucdp, "records.parquet")
```

JSON bundles are the canonical interchange format and contain schema/library
versions, provenance, validation issues, and integrity fingerprints. Run loading
recomputes candidates and verifies their IDs. Parquet carries dataset metadata in
the file schema and supports `read_parquet` round trips, including empty datasets.
Plain normalised CSV is a convenience table; retain its JSON bundle for full
provenance and validation reports. Review CSV includes the run ID; retain the run
bundle to reconstruct original inputs and matching settings.

Writers refuse existing destinations unless explicitly passed `overwrite=True`.
Parent directories must exist. Writes use temporary files and atomic publication;
CSV/JSON/Parquet serialization failures do not truncate an existing target.

## Evaluation

`ccrt.evaluation.evaluate_candidates(result, true_pairs)` compares candidate ID
pairs with an **exhaustive** set of true `(left_source_id, right_source_id)` links
for these bounded datasets. It reports true/false positives, missed links, precision,
and recall. Empty denominators yield `None`. It evaluates candidate retrieval,
not reviewer accuracy or casualty totals. Do not pass partially reviewed labels.
