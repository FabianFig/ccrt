# Contributing and learning

Install `.[tables,dev]` into a virtual environment. Run `python -m pytest`,
`ruff check .`, and `ruff format --check .` before proposing a change. Tests use
invented examples and mocked HTTP; they must never require private data or API keys.

Work on one behaviour at a time: explain the requirement, inspect its source
contract, write a test that demonstrates the behaviour, implement it, and review
its effect on real research assumptions. Good first exercises are in the notebook.

New source adapters need a documented field mapping and source codebook reference,
fixtures that can be distributed, validation for malformed input, and a round-trip
provenance test. Do not infer civilian deaths from total deaths. Changes to date
uncertainty or candidate ranking need an updated algorithm ID and evaluation notes.
Reports of matching quality need independently adjudicated reference labels from a
declared sample; synthetic metrics and partially reviewed candidates are not
real-data accuracy estimates. Keep source records and evidence within their access
and redistribution terms.

Open a GitHub issue with the version, a minimal synthetic reproduction, expected
behaviour, and actual behaviour. Remove credentials and private source material.
We aim to review contributions as maintainer time allows; no support response SLA
is offered for the preview. Python 3.10–3.14 are tested in CI; optional pandas and
PyArrow support is tested separately from the core installation.
