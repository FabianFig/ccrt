# Changelog

## 0.1.0

- Added source-preserving UCDP GED CSV/API and ACLED event CSV adapters, validation
  reports, explicit snapshot versions, and input fingerprints.
- Added bounded authenticated API paging/retries with mocked failure tests and
  verified the live endpoint's zero-based page numbering.
- Preserved published UCDP fatality estimates that fall outside low/best/high
  numerical order, with a warning for each affected record.
- Replaced automatic one-to-one assignment with all candidate links, date intervals,
  precision warnings, coarse-location handling, and explicit review decisions.
- Added JSON run/review bundles, review CSV import/export, nullable pandas tables,
  and metadata-preserving Parquet.
- Added a resumable terminal reviewer that groups competing candidates and displays
  the original source accounts while saving each decision.
- Added an optional experimental full-screen review dashboard using terminal curses,
  isolated from the review data model for easy removal.
- Added review reports with candidate coverage, unique-record counts, unlinked
  reasons, and accepted-link diagnostics. Partial reviews never produce precision
  or recall metrics.
- Added installed-wheel workflow checks for core and tables installations, and
  extended package CI beyond the CLI help check.
- Added MIT licensing, CLI subcommands, tutorial notebook, synthetic evaluation,
  benchmark tooling, CI, and package build checks.

### Migration from the unreleased initial prototype

`Incident` is replaced by `SourceRecord`; `load_csv` now returns a `Dataset`.
`reconcile(left, right, config=MatchConfig(...))` accepts datasets and returns
`.candidates` plus `.unlinked`, replacing greedy `.matches` and unmatched lists.
Use `total_deaths_low/best/high` and `civilian_deaths` explicitly. The CLI now uses
`import`, `fetch-ucdp`, `match`, `review`, and `export` subcommands. These changes
precede the first public release; no backward-compatibility shim is provided.

### Validation scope

`0.1.0` is an experimental library. Independent real-data linkage
evaluation is not a publication gate for the library, but remains necessary before
claiming empirical matching accuracy. A prior UCDP GED 26.1 Iraq 2020 query
retrieved 282 records with 10 validation warnings; a real ACLED export supplied
6,306 filtered Iraq 2020 records with no import issues. Candidate generation
produced 1,329 pairs. Partial manual reviews do not establish precision or recall.
See `docs/releasing.md` for the publication procedure.
