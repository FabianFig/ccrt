# Source mappings and research assumptions

The unit of storage is a **source account**, not a confirmed shared event. A stable
key combines source name, source version/export label, and source record ID.
Original columns remain in `raw_json`; `record.raw` returns a fresh dictionary.
A file fingerprint identifies the exact input bytes. Metadata records the adapter
revision and, for API responses, the query and retrieval timestamp.

## Supported input contracts

UCDP GED CSV/API: versions 25.1 and 26.1, documented modern field names. ACLED:
event CSV exports using the lowercase fields described by the 2024/current
codebook. Aggregated, dyadic, legacy uppercase, or manually renamed exports are
not automatically interpreted. ACLED `version` is your export snapshot label.
Contract support is tested with synthetic fixtures; it does not imply completed
validation against every real export of those versions.

| Meaning | UCDP GED | ACLED event export |
| --- | --- | --- |
| Identity | `id` | `event_id_cnty` |
| Date interval | `date_start`, `date_end` | inferred from `event_date`, `time_precision` |
| Date precision | `date_prec`, original code | `time_precision`, original code |
| Location | `latitude`, `longitude` | `latitude`, `longitude` |
| Location precision | `where_prec`, original code | `geo_precision`, original code |
| Country label | `country` | `country` |
| Principal actors | `side_a`, `side_b` | `actor1`, `actor2` |
| Source classification | `type_of_violence` as text | `event_type` |
| Total death estimate | `low`, `best`, `high` | `fatalities` → `total_deaths_best` |
| Civilian deaths | `deaths_civilians` | absent; left unknown |
| Narrative, attribution, admin areas, source references, other fields | preserved in raw account | preserved in raw account |

These classifications and precision numbers are not interchangeable across
sources. UCDP's total bounds are not civilian casualty bounds. ACLED fatalities
are source-coded reported fatalities; zero can mean no fatality information was
reported. Neither zero nor an empty value is reinterpreted. The generic CSV
adapter interprets its legacy `fatalities_min/max` columns as total bounds only.
Some published UCDP records have low/best/high values outside numerical order.
CCRT retains those original figures and reports a validation warning; it does not
sort them or manufacture a corrected range.

## Date and location policy

UCDP intervals are kept as published. ACLED precision 1 uses its reference date;
precision 2 creates a ±3-day search envelope; precision 3 creates the containing
calendar-month envelope. These are CCRT search assumptions, not newly discovered
incident dates. The exact reference date remains in `raw_json`; `date_basis`
labels inferred intervals. Blank precision retains the reference date and adds
uncertainty to candidate warnings.

Missing dates or coordinates are retained, with a warning and an unlinked reason.
Coordinates are checked for finite values and valid latitude/longitude ranges.
Zero coordinates remain valid. Geographic codes are not converted to radii.
By default, codes >=3 in either supported source prevent matching because those
representations may be too broad for point-distance comparisons. Users can opt in
and inspect uncertainty warnings. This choice can miss true matches.

## Candidate selection and ranking

`interval-haversine-v1` retains every eligible cross-source pair within the
configured date and distance limits. Date distance is the gap between closed
intervals, or zero when they overlap. Geographic distance is the great-circle
distance between reported coordinates, not an event boundary. When both country
labels are present, they must agree after trimming and case folding. Explicit
country aliases can bridge naming differences; CCRT does not infer actor or
country equivalence.

The default limits are three days and 25 km. Eligible pairs receive the score
`1 - (days_apart / (max_days + 1) + distance_km / max_km) / 2` and are ordered by
that score. Actor names and casualty claims do not affect it. It is an uncalibrated
proximity ranking, not a match probability. Broad date intervals can yield many
high-scoring candidates, and the default exclusions can miss true links. See the
[usage guide](usage.md#generate-candidates) for CLI settings.

## Validation and provenance

Strict loading raises `ValidationError` with all invalid-row reports. With
`errors='collect'`, valid accounts are returned alongside error reports containing
the rejected rows. Duplicate IDs are errors; collect mode retains the first valid
occurrence and reports subsequent duplicates. No duplicate is silently merged.
Missing required headers, repeated headers, and malformed CSV widths fail the
file import. Dates must be ISO dates or ISO timestamps; ambiguous locale dates
are rejected. Unknown extra fields are preserved.

Source events can have different inclusion rules, observation periods, aggregation,
and attribution. Comparing raw totals does not by itself measure under-reporting.
Accepted links record a researcher's judgment and do not remove those differences.
References to Airwars or any other publisher remain provenance, not credibility labels.

## Primary references

- [UCDP GED 26.1 codebook](https://ucdp.uu.se/downloads/ged/ged261.pdf): event definitions, variables, precision, and citation instructions.
- [UCDP API](https://ucdp.uu.se/apidocs/): authentication, paging, versioning, and filter semantics.
- [ACLED codebook](https://acleddata.com/methodology/acled-codebook): event columns, date/location precision, and fatality coding.

Mapping notes checked 2026-09-24. Users should cite the datasets and codebooks
appropriate to their actual exports; the software licence does not license data.
The [UCDP download center](https://ucdp.uu.se/downloads/) states its current dataset
licence and citation requirements. ACLED's current
[EULA](https://acleddata.com/eula), [content usage terms](https://acleddata.com/contentusage),
and [attribution policy](https://acleddata.com/attributionpolicy) apply to users of
its data. In particular, CCRT distributions must not include ACLED source records.
