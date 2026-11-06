import math

import pytest

from multiobjective_algorithms import ObjectiveSpec, spread_delta, summarize_run_spread

MIN_F1_F2 = (
    ObjectiveSpec("f1", "minimize"),
    ObjectiveSpec("f2", "minimize"),
)
EXTREMES = ((0.0, 1.0), (1.0, 0.0))


def test_uniform_front_has_delta_zero() -> None:
    front = [(0.0, 1.0), (0.5, 0.5), (1.0, 0.0)]

    assert spread_delta(front, EXTREMES) == pytest.approx(0.0)


def test_concentrated_front_is_worse_than_a_uniform_front() -> None:
    concentrated = [(0.0, 1.0), (0.1, 0.9), (1.0, 0.0)]
    uniform = spread_delta([(0.0, 1.0), (0.5, 0.5), (1.0, 0.0)], EXTREMES)
    value = spread_delta(concentrated, EXTREMES)

    assert value == pytest.approx(0.8)
    assert value > uniform


def test_a_front_with_fewer_than_two_points_has_no_spread() -> None:
    assert spread_delta([(0.2, 0.8)], EXTREMES) == 1.0
    assert spread_delta([], EXTREMES) == 1.0


def test_normalized_spread_ignores_absolute_objective_scales() -> None:
    compact = summarize_run_spread(
        (
            {"round": 1, "f1": 0.0, "f2": 1.0},
            {"round": 1, "f1": 0.5, "f2": 0.5},
            {"round": 1, "f1": 1.0, "f2": 0.0},
        ),
        MIN_F1_F2,
    )
    stretched = summarize_run_spread(
        (
            {"round": 1, "f1": 10.0, "f2": 4000.0},
            {"round": 1, "f1": 12.0, "f2": 2000.0},
            {"round": 1, "f1": 14.0, "f2": 0.0},
        ),
        MIN_F1_F2,
    )

    assert compact.rounds[0].spread == pytest.approx(0.0)
    assert stretched.rounds[0].spread == pytest.approx(compact.rounds[0].spread)


def test_a_single_round_has_sample_standard_deviation_zero() -> None:
    summary = summarize_run_spread(
        (
            {"round": 1, "f1": 0.0, "f2": 1.0},
            {"round": 1, "f1": 0.1, "f2": 0.9},
            {"round": 1, "f1": 1.0, "f2": 0.0},
        ),
        MIN_F1_F2,
    )

    assert summary.mean_spread == pytest.approx(0.8)
    assert summary.sample_stdev_spread == 0.0
    assert summary.coefficient_of_variation == 0.0


def test_run_spread_uses_the_union_extremes_and_the_sample_aggregates() -> None:
    summary = summarize_run_spread(
        (
            {"round": 1, "f1": 0.0, "f2": 4.0},
            {"round": 1, "f1": 4.0, "f2": 0.0},
            {"round": 1, "f1": 5.0, "f2": 5.0},
            {"round": 2, "f1": 1.0, "f2": 3.0},
            {"round": 2, "f1": 3.0, "f2": 1.0},
        ),
        MIN_F1_F2,
    )

    assert summary.rounds[0].candidate_count == 2
    assert summary.rounds[0].spread == pytest.approx(0.0)
    assert summary.rounds[1].candidate_count == 2
    assert summary.rounds[1].spread == pytest.approx(0.5)
    assert summary.mean_spread == pytest.approx(0.25)
    assert summary.sample_stdev_spread == pytest.approx(math.sqrt(0.125))
    assert summary.coefficient_of_variation == pytest.approx(summary.sample_stdev_spread / summary.mean_spread)


def test_a_zero_mean_spread_leaves_the_coefficient_undefined() -> None:
    summary = summarize_run_spread(
        (
            {"round": 1, "f1": 0.0, "f2": 1.0},
            {"round": 1, "f1": 1.0, "f2": 0.0},
            {"round": 2, "f1": 0.0, "f2": 1.0},
            {"round": 2, "f1": 1.0, "f2": 0.0},
        ),
        MIN_F1_F2,
    )

    assert summary.mean_spread == pytest.approx(0.0)
    assert summary.sample_stdev_spread == pytest.approx(0.0)
    assert summary.coefficient_of_variation is None


def test_maximization_is_normalized_before_the_spread() -> None:
    summary = summarize_run_spread(
        (
            {"round": 1, "quality": 5.0, "cost": 1.0},
            {"round": 1, "quality": 1.0, "cost": 0.0},
        ),
        (
            ObjectiveSpec("quality", "maximize"),
            ObjectiveSpec("cost", "minimize"),
        ),
    )

    assert summary.rounds[0].spread == pytest.approx(0.0)
