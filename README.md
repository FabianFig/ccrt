# Conflict Casualty Reconciliation Toolkit (CCRT)

CCRT helps researchers compare source accounts of conflict incidents. Import UCDP
and ACLED records, inspect possible links, record review decisions, and export
results while preserving the sources' original claims.

**Status: 0.1.0rc1, an unpublished research preview.** The planned 0.1.0 release is
an experimental library for importing source accounts and reviewing candidate links.
Offline tests and synthetic examples exercise the software. A live UCDP query and a
real ACLED CSV import have been checked, but no independent real-data study has
measured linkage accuracy. Scores rank candidates; they are not probabilities or
measures of source credibility. CCRT does not establish event identity, combine
casualty counts, estimate underreporting, or establish responsibility for an incident.

## Install from this repository

Python 3.10–3.14 is the supported target. From the repository root:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# fish shell:
source .venv/bin/activate.fish
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

This core installation needs HTTPX and python-dotenv. Use
`python -m pip install -e '.[tables]'` for pandas and PyArrow exports, or
`python -m pip install -e '.[tables,dev]'` to run the full development checks.
This project has not yet been published to PyPI. Install from this repository
until the maintainer announces a distribution name and release.

## Quickstart with invented records

These files contain invented incidents in **Exampleland**, not real casualty data.
Run these commands from the repository root with an empty `work/` directory. CCRT
refuses to overwrite existing outputs.

```bash
mkdir -p work
ccrt import ucdp examples/ucdp_synthetic.csv work/ucdp.json --version 26.1
ccrt import acled examples/acled_synthetic.csv work/acled.json --version synthetic-2026-09-24
ccrt match work/ucdp.json work/acled.json work/matches
```

This produces three candidate links and four unlinked source records. Two
candidates compete for U1: both stay visible. Unlinked records include missing
coordinates, excluded coarse locations, and records with no candidate under these
settings. This example can be reproduced without an API key or real source data.

`ccrt match` creates `work/matches/candidates.csv`, `run.json`, and `review.json`.
The CSV contains proposed links and unlinked source records.

For larger runs, review in the terminal instead of editing the wide CSV:

```bash
ccrt review-interactive work/matches/run.json work/matches/session.json --from-existing work/matches/review.json --reviewer "Your name"
```

The command groups proposals by the left source record, shows competing candidates,
and displays each source's original notes, actors, dates, coordinates, location,
and fatalities. Inspecting a candidate also shows the coordinate separation and
date gap beside the matching limits. There are no separate latitude and longitude
scores; both coordinates feed one great-circle distance.
Choose a numbered candidate to inspect it, then `a` to accept, `r` to reject,
`u` to leave unresolved, or `b` to return to the group. `n`/`p` move between groups;
`q` exits. At the end of the queue, `n` returns to the first group. Each decision
is saved immediately. To resume, run the same command without `--from-existing`.
By default it includes groups that still contain unresolved candidates. Use `--all`
to include decided groups or `--left-id U1` to start at a particular source record
and then move through the queue. A score is only a proximity rank;
read both accounts before deciding. The review JSON can be passed to
`ccrt export --review` directly.

An **experimental full-screen dashboard** is also available:

```bash
ccrt review-tui work/matches/run.json work/matches/dashboard.json --from-existing work/matches/review.json --reviewer "Your name"
```

It has three panes for source groups, candidates, and source details. Left/right
arrows change groups; up/down arrows change candidates; Page Up/Page Down scroll
the details. Press `a`, `r`, or `u` to decide, `e` to edit a note, `f` to toggle
decided groups, `g` to jump to a source ID, and `q` to quit. Decisions save to
the review JSON immediately. To resume, omit `--from-existing`. The dashboard
uses Python's terminal curses support and requires an interactive terminal.
It is separate from the matching and review data formats.

The CSV workflow is also available. Make a copy before editing:

```bash
cp work/matches/candidates.csv work/reviewed.csv
```

Open `work/reviewed.csv` in a spreadsheet editor or text editor. For the **three
candidate rows**, edit `status`, `reviewer`, and optionally `note`. The invented
examples have these known outcomes:

| Left | Right | Set `status` to | Set `reviewer` to |
| --- | --- | --- | --- |
| U1 | A1 | `accepted` | Your name |
| U1 | A2 | `rejected` | Your name |
| U2 | A3 | `accepted` | Your name |

Leave `unlinked` rows as they are. `reviewed_at` can stay blank; CCRT fills it
when importing a decided row. Every `accepted` or `rejected` row needs a
nonempty reviewer. Keep the other columns intact, then run:

```bash
ccrt review work/matches/run.json work/reviewed.json --csv work/reviewed.csv
ccrt export work/matches/run.json work/final.csv --format review-csv --review work/reviewed.json
ccrt export work/ucdp.json work/ucdp.parquet --format parquet
```

The first command creates `work/reviewed.json`; the second command reads that
file. If you want to inspect the proposals before deciding, you can also export
an unresolved table directly:

```bash
ccrt export work/matches/run.json work/unresolved.csv --format review-csv
```

CCRT verifies run IDs and candidate IDs when importing reviews. Changes to the
source columns in the review CSV are ignored; the run's original accounts remain
authoritative. Review CSVs can repeat a source record across multiple proposals:
**summing casualty columns would double-count records**. Multiple accepted links
are allowed because sources may split or aggregate incidents differently.

### Check review progress

```bash
ccrt report work/matches/run.json --review work/reviewed.json --output work/review-report.json
```

Use the review JSON from your current CSV, terminal, or dashboard session. The
report shows reviewed candidate counts, unique source records with candidates,
unlinked reasons, accepted links with multiple counterparts, and differences in
reported fatalities. These diagnostics help choose records to revisit; multiple
accepted links or different counts do not by themselves establish an error.
`--output` is optional and saves a new JSON report with the run ID and review
fingerprint. It refuses an existing file.

Review coverage describes only the generated candidates. Even reviewing every
candidate cannot reveal true links that the matcher never proposed. Use exhaustive
labels for a bounded sample to measure retrieval precision and recall.

## Python API

```python
from ccrt import MatchConfig, Review, load_acled_csv, load_ucdp_csv, reconcile
from ccrt.export import write_csv
from ccrt.storage import save_run, save_review

ucdp = load_ucdp_csv("examples/ucdp_synthetic.csv", version="26.1")
acled = load_acled_csv("examples/acled_synthetic.csv", version="synthetic-2026-09-24")
result = reconcile(ucdp, acled, config=MatchConfig(max_days=3, max_km=25))
for candidate in result.candidates:
    print(
        candidate.left.source_id,
        candidate.right.source_id,
        candidate.days_apart,
        candidate.distance_km,
        candidate.warnings,
    )

review = Review.create(result)
# After inspecting the original accounts:
# review = review.decide(candidate_id, 'accepted', reviewer='Your name', note='Evidence...')
save_run(result, "run.json")
save_review(review, result, "review.json")
write_csv(result, "candidates.csv", review=review)
frame = ucdp.to_pandas()  # optional tables extra
```

See the runnable [teaching notebook](examples/reconciliation_walkthrough.ipynb),
[API reference](docs/api.md), and [source mappings](docs/source-mappings.md).
The source-specific CSV contracts are UCDP GED 25.1/26.1 with modern field names
and current lowercase ACLED event exports. ACLED's `--version` value is a label
for the exact export snapshot supplied by the user, not a verified release number.
The JSON dataset bundle retains source IDs, the snapshot label, raw fields, an
input hash, and validation issues. Keep the source file and its access terms with
your research records.

## Fetch UCDP GED

To keep your token available between sessions, create a `.env` file in the project
directory. Open it in a text editor (for example, `nano .env`) and enter one line:

```dotenv
UCDP_API_KEY=your_actual_token_here
```

Replace the placeholder with your token; do not share the file. `.env` is already
excluded by this repository's `.gitignore`. On Unix systems, `chmod 600 .env`
limits who can read it. From the project directory, `ccrt fetch-ucdp` reads this
file automatically. An existing `UCDP_API_KEY` environment variable takes
precedence. Use `--env-file /path/to/private.env` when running from another
directory. The Python `UCDPClient` continues to use an environment variable or an
explicit `api_key=` argument. CCRT never stores the token in dataset bundles.

```bash
ccrt fetch-ucdp work/ucdp-iraq.json --version 26.1 --country 645 --start-date 2020-01-01 --end-date 2020-12-31
```

Country values are UCDP/Gleditsch-Ward IDs, not ISO codes. UCDP's `StartDate` and
`EndDate` filter **date_end**, so they do not perform a general interval-overlap
query. CCRT requests numbered pages from the fixed UCDP host, checks pagination
consistency, and fails on incomplete results. Save the JSON bundle to reuse data
offline. Each user supplies their own token. See [UCDP API documentation](https://ucdp.uu.se/apidocs/).

## What the matching rules mean

- Dates are intervals. The temporal distance is the number of days between them,
  or zero when they overlap. ACLED week/month intervals are explicitly inferred.
- Distances are spherical great-circle distances between reported coordinates,
  not distances between known event boundaries.
- UCDP and ACLED location precision codes of 3 or higher are excluded by default.
  Set `include_coarse_locations=True` only after considering the source geometry.
- Countries must agree after trimming and case folding when both are present.
  Explicit `country_aliases` can bridge source naming differences; no automatic
  fuzzy country or actor matching is performed.
- All eligible pairs survive. The heuristic score is
  `1 - (days_apart / (max_days + 1) + distance_km / max_km) / 2`.
  It ignores casualty agreement and actor names, which remain available for review.

Defaults of three days and 25 km are starting settings, not validated universal
thresholds. Broad intervals can generate many candidates with high scores. See
[validation and performance](docs/validation.md) before interpreting results.

## Contributing and release status

```bash
python -m pytest
ruff check .
ruff format --check .
python -m build
python -m twine check dist/*
```

Read [CONTRIBUTING.md](CONTRIBUTING.md), the [release checklist](docs/releasing.md),
[validation notes](docs/validation.md), and [CHANGELOG.md](CHANGELOG.md). The
pre-release API replaces the initial generic CSV prototype; migration details are
in the changelog. Airwars and IBC adapters,
claim-credibility models, casualty aggregation, and predictive models are outside
this release.

The code and synthetic examples use the [MIT license](LICENSE). UCDP and ACLED
data remain subject to their respective access, attribution, and reuse terms.
Researchers must obtain their own source access and check the terms for the
snapshot they use. Do not redistribute ACLED source records with CCRT results.
