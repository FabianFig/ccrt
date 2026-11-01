# Release procedure

Version `0.1.0` is an experimental research library. It promises installable
UCDP GED and ACLED event import, source-preserving dataset bundles, inspectable
candidate generation, human review, and exports as documented in the README and
API guide. It does not promise that candidate links are correct, that scores are
probabilities, or that source casualty claims can be combined. Building a wheel
does not validate a matching method. Publication requires a maintainer-approved
GitHub release and approval of the protected `pypi` environment.

## Gates for an experimental public 0.1.0

- Complete the existing offline test, lint, notebook, build, and installed-wheel
  checks. Review actual CI results on the intended release commit.
- Check that the README quickstart, Python API examples, CLI help, source mapping
  notes, and distribution metadata agree with the code. Make the lack of measured
  real-data linkage accuracy explicit in the README, package description, and
  validation notes.
- Inspect the wheel and source archive for expected code, documentation, and
  synthetic examples, and for the absence of `.env`, `work/`, restricted source
  records, credentials, and local research annotations.
- Check the current terms and attribution requirements for the source datasets.
  The [UCDP download center](https://ucdp.uu.se/downloads/) describes its dataset
  licence and required citations. ACLED's [EULA](https://acleddata.com/eula),
  [content usage terms](https://acleddata.com/contentusage), and
  [attribution policy](https://acleddata.com/attributionpolicy) govern use of its
  data. Do not bundle ACLED source records or assume the code licence covers data.
- Verify the intended PyPI distribution name and maintainer ownership immediately
  before upload. A 404 from a public project lookup does not reserve the name.
  [PyPI's naming guidance](https://docs.pypi.org/project-management/choosing-a-name/)
  explains why an unseen name may still be unavailable. Change `pyproject.toml`
  if the name cannot be claimed; the import package can remain `ccrt`.
- Confirm that `ccrt/_version.py`, the changelog, release wording, and distribution
  metadata all identify `0.1.0`. Repeat package checks on the exact release commit.

The earlier live UCDP query and ACLED CSV import in `docs/validation.md` are useful
mapping checks, not proof of linkage accuracy. Rechecking live data is appropriate
when making a claim about the current endpoint or a new source snapshot; it is not
a prerequisite for publishing the offline library. No independent real-data
annotation study is required for this experimental release.

## Scientific validation remains separate

Before claiming empirical candidate-retrieval precision or recall on UCDP–ACLED
data, use a bounded frame selected independently of the matcher, independently
adjudicated reference labels, and an analysis of missed and false links, thresholds,
and excluded records. Draft correspondence and annotation protocols remain internal
while their research-lead decisions are pending. Operational accepted-link accuracy
needs a separate decision set and is outside the initial release evaluation. The
synthetic results in `docs/validation.md` demonstrate software behaviour, not
real-data accuracy.

## Build, inspect, and distribute

```bash
python -m pytest
ruff check .
ruff format --check .
python -m build
python -m twine check dist/*
```

Build from a clean checkout, install the wheel in a fresh environment, and run
`ccrt --help` plus the offline example outside the source directory. Test both core
and `tables` installations. Review the wheel/sdist file inventory. The CI build
artifact is available for inspection after passing checks.

Use `benchmarks/smoke_install.py` with the fresh environment's Python, while
working outside the checkout. It runs the synthetic CLI workflow and verifies
that imports resolve to the installed distribution. Run it first with only the
core wheel dependencies, then install that wheel's `tables` extra and repeat with
`--tables`. The package CI job performs both modes. Keep generated build outputs
out of Git; upload the intended wheel/source archive only when publishing.

## Final publication sequence

1. Review release changes in a pull request against the public repository's
   protected `main` branch. Keep private source data and research drafts out of it.
2. Confirm the `ccrt` PyPI name and publishing access. A missing public project
   page does not establish that the name can be registered.
3. Merge the version change only after CI passes. Inspect the wheel and source
   archive produced from the resulting `main` commit.
4. Configure the matching PyPI Trusted Publisher for `FabianFig/ccrt`, workflow
   `publish.yml`, and environment `pypi`. With maintainer approval, tag the tested
   commit as `v0.1.0` and publish its GitHub release. The release workflow checks
   the tag, the successful `main` CI run, and both distributions before awaiting
   approval in the protected `pypi` environment and uploading to PyPI.
5. Install the published `ccrt==0.1.0` wheel in a fresh environment outside the
   checkout and repeat the installed-package smoke test. Confirm the public
   project page, metadata, and artifact hashes.

Do not upload a package solely because a local wheel built successfully.
Before 1.0, document breaking changes; after 1.0, use semantic versioning and a
published deprecation period for public API removals. Issues and reproducible bug
reports are the initial monitoring mechanism; the library has no telemetry.
