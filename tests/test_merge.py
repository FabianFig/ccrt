import random
from dataclasses import replace
from datetime import date, timedelta

import pytest
from conftest import dataset, record

from ccrt import MatchConfig, reconcile
from ccrt.merge import distance_km


def test_candidates_keep_ambiguity(source_pair):
    result = reconcile(*source_pair)
    pairs = {(c.left.source_id, c.right.source_id) for c in result.candidates}
    assert pairs == {("U1", "A1"), ("U1", "A2"), ("U2", "A3")}
    reasons = {u.record.source_id: u.reason for u in result.unlinked}
    assert reasons == {
        "U3": "coarse_location_excluded",
        "U4": "missing_coordinates",
        "A4": "coarse_location_excluded",
        "A5": "no_candidate",
    }
    assert (
        "right_date_interval_inferred"
        in next(c for c in result.candidates if c.right.source_id == "A3").warnings
    )


def test_coarse_opt_in(source_pair):
    result = reconcile(*source_pair, config=MatchConfig(include_coarse_locations=True))
    assert ("U3", "A4") in {(c.left.source_id, c.right.source_id) for c in result.candidates}


def test_interval_overlap_and_boundary():
    left = dataset("a", [record("a", start=date(2020, 1, 1), end=date(2020, 2, 1))])
    right = dataset("b", [record("b", start=date(2020, 1, 20))])
    assert reconcile(left, right, config=MatchConfig(max_days=0)).candidates[0].days_apart == 0
    outside = dataset("b", [record("b", start=date(2020, 2, 4))])
    assert len(reconcile(left, outside, config=MatchConfig(max_days=3)).candidates) == 1
    assert not reconcile(left, outside, config=MatchConfig(max_days=2)).candidates


def test_haversine_antimeridian_and_poles():
    a = record("a", longitude=179.99)
    b = record("b", longitude=-179.99)
    assert distance_km(a, b) == pytest.approx(2.2239, abs=0.001)
    assert distance_km(record("a", latitude=90), record("b", latitude=90, longitude=180)) < 1e-6


def test_country_alias_and_missing_country():
    left = dataset("a", [record("a", country="Yemen (North Yemen)")])
    right = dataset("b", [record("b", country="Yemen")])
    assert not reconcile(left, right).candidates
    config = MatchConfig(country_aliases={"Yemen (North Yemen)": "Yemen"})
    assert len(reconcile(left, right, config=config).candidates) == 1
    with pytest.raises(TypeError):
        config.country_aliases["foo"] = "bar"
    blank = dataset("b", [record("b", country="")])
    assert "country_missing" in reconcile(left, blank).candidates[0].warnings


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_days": -1},
        {"max_days": 1.5},
        {"max_days": True},
        {"max_km": 0},
        {"max_km": float("nan")},
        {"max_km": float("inf")},
    ],
)
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        MatchConfig(**kwargs)


def test_same_source_rejected():
    a = dataset("a", [record("a")])
    with pytest.raises(ValueError, match="distinct sources"):
        reconcile(a, a)


def test_empty_and_missing_dates():
    left = dataset("a", [record("a", start=None)])
    right = dataset("b", [])
    result = reconcile(left, right)
    assert not result.candidates
    assert result.unlinked[0].reason == "missing_date"


def test_input_order_does_not_change_candidates(source_pair):
    left, right = source_pair
    first = reconcile(left, right)
    second = reconcile(
        replace(left, records=tuple(reversed(left.records))),
        replace(right, records=tuple(reversed(right.records))),
    )
    assert first.run_id == second.run_id
    assert first.candidates == second.candidates


def test_interval_index_matches_exhaustive_reference():
    rng = random.Random(10)

    def records(source):
        result = []
        for i in range(100):
            start = date(2020, 1, 1) + timedelta(days=rng.randrange(365))
            result.append(
                record(
                    source,
                    str(i),
                    start=start,
                    end=start + timedelta(days=rng.randrange(50)),
                    latitude=rng.uniform(0, 0.5),
                    longitude=rng.uniform(0, 0.5),
                )
            )
        return result

    left, right = dataset("a", records("a")), dataset("b", records("b"))
    actual = {(c.left.source_id, c.right.source_id) for c in reconcile(left, right).candidates}
    expected = {
        (a.source_id, b.source_id)
        for a in left
        for b in right
        if max(0, (a.date_start - b.date_end).days, (b.date_start - a.date_end).days) <= 3
        and distance_km(a, b) <= 25
    }
    assert actual == expected
