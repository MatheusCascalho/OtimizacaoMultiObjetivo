import math

import pytest

from multiobjective_algorithms import (
    ObjectiveSpec,
    ReferencePointError,
    hypervolume_2d,
    shift_reference_point,
    summarize_run_hypervolume,
)
from multiobjective_algorithms.hypervolume import coefficient_of_variation

MIN_F1_F2 = (
    ObjectiveSpec("f1", "minimize"),
    ObjectiveSpec("f2", "minimize"),
)


def test_reference_point_is_applied_after_normalization() -> None:
    samples = (
        {"round": 1, "f1": 0.0, "f2": 4.0},
        {"round": 1, "f1": 4.0, "f2": 0.0},
        {"round": 1, "f1": 5.0, "f2": 5.0},
        {"round": 2, "f1": 1.0, "f2": 3.0},
        {"round": 2, "f1": 3.0, "f2": 1.0},
    )

    summary = summarize_run_hypervolume(samples, MIN_F1_F2)

    assert summary.nadir == (4.0, 4.0)
    assert summary.reference_point == pytest.approx((1.1, 1.1))
    assert summary.reference_shift == 1.1
    assert shift_reference_point((1.0, 1.0)) == pytest.approx((1.1, 1.1))
    assert summary.rounds[0].round_index == 1
    assert summary.rounds[0].candidate_count == 2
    assert summary.rounds[0].hypervolume == pytest.approx(0.21)
    assert summary.rounds[1].candidate_count == 2
    assert summary.rounds[1].hypervolume == pytest.approx(0.4725)


def test_hypervolume_rectangles_match_the_normalized_definition() -> None:
    area = hypervolume_2d([(0.0, 1.0), (1.0, 0.0)], (1.1, 1.1))
    assert area == pytest.approx((1.0 - 0.0) * (1.1 - 1.0) + (1.1 - 1.0) * (1.1 - 0.0))
    assert area == pytest.approx(0.21)


def test_normalized_hypervolume_ignores_absolute_objective_scales() -> None:
    compact = summarize_run_hypervolume(
        (
            {"round": 1, "f1": 0.0, "f2": 4.0},
            {"round": 1, "f1": 4.0, "f2": 0.0},
            {"round": 2, "f1": 1.0, "f2": 3.0},
            {"round": 2, "f1": 3.0, "f2": 1.0},
        ),
        MIN_F1_F2,
    )
    stretched = summarize_run_hypervolume(
        (
            {"round": 1, "f1": 10.0, "f2": 4000.0},
            {"round": 1, "f1": 14.0, "f2": 0.0},
            {"round": 2, "f1": 11.0, "f2": 3000.0},
            {"round": 2, "f1": 13.0, "f2": 1000.0},
        ),
        MIN_F1_F2,
    )

    assert stretched.reference_point == pytest.approx((1.1, 1.1))
    assert stretched.rounds[0].hypervolume == pytest.approx(compact.rounds[0].hypervolume)
    assert stretched.rounds[1].hypervolume == pytest.approx(compact.rounds[1].hypervolume)
    assert stretched.rounds[0].hypervolume == pytest.approx(0.21)


def test_aggregates_use_the_sample_standard_deviation() -> None:
    summary = summarize_run_hypervolume(
        (
            {"round": 1, "f1": 0.0, "f2": 4.0},
            {"round": 1, "f1": 4.0, "f2": 0.0},
            {"round": 2, "f1": 1.0, "f2": 3.0},
            {"round": 2, "f1": 3.0, "f2": 1.0},
        ),
        MIN_F1_F2,
    )

    assert summary.mean_hypervolume == pytest.approx((0.21 + 0.4725) / 2)
    assert summary.sample_stdev_hypervolume == pytest.approx(math.sqrt(((0.21 - 0.34125) ** 2) * 2))
    assert summary.coefficient_of_variation == pytest.approx(
        summary.sample_stdev_hypervolume / summary.mean_hypervolume
    )
    assert summary.mean_candidate_count == pytest.approx(2)
    assert summary.rounds[0].distance_to_mean == pytest.approx(0.21 - 0.34125)
    assert summary.rounds[1].distance_to_mean == pytest.approx(0.4725 - 0.34125)


def test_a_single_round_has_sample_standard_deviation_zero() -> None:
    summary = summarize_run_hypervolume(
        ({"round": 1, "f1": 0.0, "f2": 4.0}, {"round": 1, "f1": 4.0, "f2": 0.0}),
        MIN_F1_F2,
    )

    assert summary.sample_stdev_hypervolume == 0.0
    assert summary.coefficient_of_variation == 0.0
    assert summary.rounds[0].distance_to_mean == 0.0


def test_coefficient_of_variation_is_absent_when_the_mean_is_zero() -> None:
    summary = summarize_run_hypervolume(
        (
            {"round": 1, "f1": 0.0, "f2": 0.0},
            {"round": 2, "f1": 0.0, "f2": 0.0},
        ),
        MIN_F1_F2,
    )

    assert summary.mean_hypervolume == 0.0
    assert summary.coefficient_of_variation is None
    assert coefficient_of_variation(0.0, 1.5) is None


def test_maximization_shifts_toward_the_worse_side_and_keeps_the_area() -> None:
    summary = summarize_run_hypervolume(
        (
            {"round": 1, "quality": 5.0, "cost": 1.0},
            {"round": 1, "quality": 1.0, "cost": 0.0},
        ),
        (
            ObjectiveSpec("quality", "maximize"),
            ObjectiveSpec("cost", "minimize"),
        ),
    )

    assert summary.nadir == pytest.approx((1.0, 1.0))
    assert summary.reference_point == pytest.approx((1.1, 1.1))
    assert summary.rounds[0].hypervolume == pytest.approx(0.21)
    assert summary.rounds[0].candidate_count == 2


def test_a_null_range_keeps_the_normalized_reference_at_zero() -> None:
    assert shift_reference_point((0.0, 1.0)) == pytest.approx((0.0, 1.1))
    summary = summarize_run_hypervolume(
        ({"round": 1, "f1": 2.0, "f2": 3.0},),
        MIN_F1_F2,
    )
    assert summary.reference_point == pytest.approx((0.0, 0.0))
    assert summary.rounds[0].hypervolume == 0.0


def test_empty_sample_is_rejected() -> None:
    with pytest.raises(ReferencePointError, match="Não há soluções"):
        summarize_run_hypervolume((), MIN_F1_F2)
