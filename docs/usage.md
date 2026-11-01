# Using CCRT

The [README quickstart](../README.md#quickstart) creates `work/ucdp.json`,
`work/acled.json`, and a match run in `work/matches/` from invented records. The
commands below continue that example. Output paths must be unused unless a command
explicitly resumes a review session.

## Import source records

```bash
ccrt import ucdp examples/ucdp_synthetic.csv work/ucdp.json --version 26.1
ccrt import acled examples/acled_synthetic.csv work/acled.json --version synthetic-2026-09-24
```

The UCDP adapter supports GED 25.1 and 26.1 CSV files with modern field names.
The ACLED adapter expects current lowercase event-export fields. For ACLED,
`--version` identifies the supplied export snapshot; it is not a release number
verified by CCRT. See [source mappings](source-mappings.md) for the input contracts.

Each JSON dataset bundle retains source IDs, raw fields, the version or snapshot
label, an input hash, and validation issues. Keep the original source file, filter
record, and access terms with your research materials. Use `--collect-errors` to
retain valid records and report invalid rows rather than stopping at an invalid
record. Missing required headers and malformed CSV structure still fail import.

## Generate candidates

```bash
ccrt match work/ucdp.json work/acled.json work/matches
```

The output directory contains `run.json`, `review.json`, and `candidates.csv`.
`run.json` binds the source bundles and matching settings; `review.json` starts
with unresolved decisions. The CSV lists candidate pairs and unlinked source
records. Two candidates can share a source record, and all eligible pairs remain
available for review.

The defaults are three days and 25 km. Change them with `--max-days` and
`--max-km`. Use `--include-coarse-locations` only after checking source precision,
or `--country-alias FROM=TO` for an explicit country-name mapping. These settings
alter candidate retrieval, not the underlying source claims. See
[source mappings](source-mappings.md#date-and-location-policy) for date and
location assumptions.

## Review candidates

### Edit a review CSV

Make a copy of `work/matches/candidates.csv` as `work/reviewed.csv`. For each
candidate row, set `status` to `accepted`, `rejected`, or `unresolved`. An accepted
or rejected row needs a non-empty `reviewer`; `note` is optional. In the invented
example, U1–A1 and U2–A3 correspond, while nearby U1–A2 is distinct. Leave
`unlinked` rows unchanged and retain the other columns. CCRT fills a blank
`reviewed_at` for decided rows.

```bash
ccrt review work/matches/run.json work/reviewed.json --csv work/reviewed.csv
```

The run's original accounts remain authoritative. Changes to source columns in
the edited CSV are ignored; run and candidate IDs are checked when the review is
imported. A source record can appear in several candidate rows. Multiple accepted
links are allowed when sources split or aggregate incidents differently.

### Review in the terminal

```bash
ccrt review-interactive work/matches/run.json work/matches/session.json \
  --from-existing work/matches/review.json --reviewer "Your name"
```

The reviewer groups candidates by left source record and shows both original
accounts, dates, locations, actors, fatalities, date gaps, and distances. Choose a
candidate number to inspect it. Use `a` to accept, `r` to reject, `u` to leave it
unresolved, `b` to return to the group, `n`/`p` to move between groups, and `q` to
quit. Decisions are saved immediately.

To resume, run the same command with `work/matches/session.json` as the output and
omit `--from-existing`. Add `--all` to include decided groups or `--left-id U1`
to start at a particular source record.

An experimental full-screen alternative uses the same review JSON format:

```bash
ccrt review-tui work/matches/run.json work/matches/dashboard.json \
  --from-existing work/matches/review.json --reviewer "Your name"
```

It needs an interactive terminal with curses support. It displays source groups,
candidates, and account details in separate panes. Left/right arrows change groups,
up/down arrows change candidates, and Page Up/Page Down scroll details. Press `a`,
`r`, or `u` to decide, `e` to edit a note, `f` to toggle decided groups, `g` to jump
to a source ID, and `q` to quit. Omit `--from-existing` when resuming the same
dashboard JSON.

## Report and export

Use the JSON produced by your CSV or terminal review:

```bash
ccrt report work/matches/run.json --review work/reviewed.json \
  --output work/review-report.json
ccrt export work/matches/run.json work/final.csv \
  --format review-csv --review work/reviewed.json
ccrt export work/ucdp.json work/ucdp.parquet --format parquet
```

The report counts reviewed candidates and unique source records, lists unlinked
reasons, and flags multiple accepted counterparts and differing fatality claims.
These are review diagnostics, not measures of linkage accuracy. `--output` is
optional. Parquet export requires the `tables` extra; use `--format csv` for a
normalised source-record table without it. To export unresolved proposals, run
`ccrt export work/matches/run.json work/unresolved.csv --format review-csv`.

Review CSVs repeat source values across candidate rows. Do not sum casualty
columns across those rows. Missing casualty values remain distinct from reported
zero, and accepting a link does not verify either source's casualty claim.

## Fetch UCDP GED

Set `UCDP_API_KEY` as an environment variable or in a `.env` file in the current
directory. The environment variable takes precedence. Use `--env-file PATH` for a
file elsewhere. Do not commit credentials; CCRT does not store the token in
exported dataset bundles.

```bash
ccrt fetch-ucdp work/ucdp-iraq.json --version 26.1 --country 645 \
  --start-date 2020-01-01 --end-date 2020-12-31
```

`--country` takes a UCDP/Gleditsch-Ward country ID, not an ISO code. The API's
start and end filters apply to `date_end`, not general interval overlap. Save the
resulting JSON bundle for offline reuse. See the [API reference](api.md) for the
Python client and [UCDP API documentation](https://ucdp.uu.se/apidocs/) for the
service contract.
