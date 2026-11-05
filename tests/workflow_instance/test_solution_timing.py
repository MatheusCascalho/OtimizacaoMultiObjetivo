import pytest

from workflow_instance.domain.solution_timing import solution_timing_kpis


def test_timing_kpis_use_mean_and_sample_standard_deviation() -> None:
    kpis = solution_timing_kpis(
        [
            {"round": 1, "attempt": 1, "duration_ms": 10},
            {"round": 1, "attempt": 2, "duration_ms": 20},
            {"round": 2, "attempt": 1, "duration_ms": 30},
        ]
    )

    assert kpis is not None
    assert kpis["unit"] == "ms"
    assert kpis["count"] == 3
    assert kpis["mean_ms"] == 20
    assert kpis["sample_stdev_ms"] == 10
    assert kpis["fastest"] == {"round": 1, "attempt": 1, "duration_ms": 10}
    assert kpis["slowest"] == {"round": 2, "attempt": 1, "duration_ms": 30}


def test_single_attempt_has_zero_standard_deviation() -> None:
    kpis = solution_timing_kpis([{"round": 3, "attempt": 4, "duration_ms": 8.5}])

    assert kpis is not None
    assert kpis["mean_ms"] == 8.5
    assert kpis["sample_stdev_ms"] == 0
    assert kpis["fastest"] == kpis["slowest"] == {"round": 3, "attempt": 4, "duration_ms": 8.5}


def test_ties_keep_the_earlier_round_and_attempt() -> None:
    kpis = solution_timing_kpis(
        [
            {"round": 2, "attempt": 2, "duration_ms": 9},
            {"round": 1, "attempt": 4, "duration_ms": 5},
            {"round": 1, "attempt": 2, "duration_ms": 5},
            {"round": 2, "attempt": 1, "duration_ms": 9},
        ]
    )

    assert kpis is not None
    assert kpis["fastest"] == {"round": 1, "attempt": 2, "duration_ms": 5}
    assert kpis["slowest"] == {"round": 2, "attempt": 1, "duration_ms": 9}


def test_empty_sample_has_no_kpis() -> None:
    assert solution_timing_kpis([]) is None
    assert solution_timing_kpis(None) is None


def test_timing_sample_rejects_invalid_duration() -> None:
    with pytest.raises(ValueError):
        solution_timing_kpis([{"round": 1, "attempt": 1, "duration_ms": -1}])
