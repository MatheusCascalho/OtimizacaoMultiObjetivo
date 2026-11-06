import pytest

from multiobjective_algorithms import (
    ObjectiveSpec,
    aggregate_quality_evolution,
    configuration_key,
    is_exact_execution,
    measure_run_indicators,
    sample_iteration_indices,
    select_iteration_moments,
    summarize_run_hypervolume,
    summarize_run_spread,
)
from multiobjective_algorithms.quality_evolution import (
    IndicatorSample,
    RunIndicatorTrack,
)

OBJECTIVES = (
    ObjectiveSpec("time", "minimize"),
    ObjectiveSpec("distance", "minimize"),
)


def test_one_hundred_iterations_are_sampled_at_each_tenth() -> None:
    assert sample_iteration_indices(100) == list(range(10, 101, 10))
    assert select_iteration_moments(range(1, 101)) == list(range(10, 101, 10))

    samples = [
        {"round": index, "time": float(index), "distance": float(101 - index)}
        for index in range(1, 101)
    ]
    measured = measure_run_indicators(samples, OBJECTIVES)

    assert [item.iteration for item in measured] == list(range(10, 101, 10))


def test_a_total_that_is_not_a_multiple_of_ten_uses_the_nearest_indices() -> None:
    assert sample_iteration_indices(25) == [3, 5, 8, 10, 13, 15, 18, 20, 23, 25]
    for total in range(1, 121):
        indices = sample_iteration_indices(total)
        assert indices == sorted(set(indices))
        assert indices[0] >= 1
        assert indices[-1] == total
        assert len(indices) == min(total, 10)


def test_fewer_than_ten_iterations_returns_every_existing_iteration() -> None:
    assert sample_iteration_indices(0) == []
    assert sample_iteration_indices(4) == [1, 2, 3, 4]
    assert select_iteration_moments([2, 4, 7]) == [2, 4, 7]
    assert len(sample_iteration_indices(4)) == 4


def test_indicator_sample_uses_the_nadir_of_the_whole_execution() -> None:
    early = [
        {"round": 1, "time": 1.0, "distance": 3.0},
        {"round": 1, "time": 3.0, "distance": 1.0},
    ]
    whole = early + [
        {"round": 2, "time": 0.0, "distance": 6.0},
        {"round": 2, "time": 6.0, "distance": 0.0},
    ]

    early_only = measure_run_indicators(early, OBJECTIVES)
    combined = measure_run_indicators(whole, OBJECTIVES)
    hypervolume = summarize_run_hypervolume(whole, OBJECTIVES)
    spread = summarize_run_spread(whole, OBJECTIVES)

    assert combined[0].hypervolume != pytest.approx(early_only[0].hypervolume)
    assert combined[0].hypervolume == pytest.approx(hypervolume.rounds[0].hypervolume)
    assert combined[1].spread == pytest.approx(spread.rounds[1].spread)
    assert [item.iteration for item in combined] == [1, 2]


def test_mean_of_two_executions_at_the_same_instant() -> None:
    key = configuration_key({"iterations": 50, "repetitions": 5, "seed": 1})
    assert key == configuration_key({"iterations": 50, "repetitions": 5, "seed": 99})
    tracks = [
        RunIndicatorTrack(
            "random-heuristic",
            key,
            (IndicatorSample(10, 0.2, 0.1), IndicatorSample(20, 0.4, 0.3)),
            exact=False,
        ),
        RunIndicatorTrack(
            "random-heuristic",
            key,
            (IndicatorSample(10, 0.4, 0.3), IndicatorSample(20, 0.8, 0.5)),
            exact=False,
        ),
    ]

    curves = aggregate_quality_evolution(tracks)

    assert len(curves) == 1
    assert curves[0].algorithm_id == "random-heuristic"
    assert curves[0].points[0].iteration == pytest.approx(10)
    assert curves[0].points[0].hypervolume == pytest.approx(0.3)
    assert curves[0].points[0].spread == pytest.approx(0.2)
    assert curves[0].points[1].iteration == pytest.approx(20)
    assert curves[0].points[1].hypervolume == pytest.approx(0.6)
    assert curves[0].points[1].spread == pytest.approx(0.4)


def test_executions_of_different_length_align_by_fraction() -> None:
    long_run = tuple(IndicatorSample(10 * step, float(step), 0.1) for step in range(1, 11))
    short_run = tuple(IndicatorSample(5 * step, 0.0, 0.5) for step in range(1, 11))
    five_run = tuple(IndicatorSample(step, 0.0, 0.0) for step in range(1, 6))
    full_run = tuple(IndicatorSample(10 * step, 2.0, 2.0) for step in range(1, 11))
    key = configuration_key({"iterations": 50})

    paired = aggregate_quality_evolution(
        [
            RunIndicatorTrack("random-heuristic", key, long_run, exact=False),
            RunIndicatorTrack("random-heuristic", key, short_run, exact=False),
        ]
    )
    uneven = aggregate_quality_evolution(
        [
            RunIndicatorTrack("random-heuristic", key, five_run, exact=False),
            RunIndicatorTrack("random-heuristic", key, full_run, exact=False),
        ]
    )
    short_only = aggregate_quality_evolution(
        [
            RunIndicatorTrack("random-heuristic", key, five_run, exact=False),
        ]
    )

    assert paired[0].points[0].iteration == pytest.approx(7.5)
    assert paired[0].points[0].hypervolume == pytest.approx(0.5)
    assert paired[0].points[9].iteration == pytest.approx(75)
    assert len(uneven[0].points) == 10
    assert uneven[0].points[0].iteration == pytest.approx(10)
    assert uneven[0].points[0].hypervolume == pytest.approx(2)
    assert uneven[0].points[1].iteration == pytest.approx((1 + 20) / 2)
    assert uneven[0].points[1].hypervolume == pytest.approx(1)
    assert uneven[0].points[9].iteration == pytest.approx((5 + 100) / 2)
    assert uneven[0].points[9].hypervolume == pytest.approx(1)
    assert len(short_only[0].points) == 5
    assert [point.iteration for point in short_only[0].points] == [1, 2, 3, 4, 5]


def test_an_exact_method_does_not_enter_the_mean_curve() -> None:
    key = configuration_key({"iterations": 50})
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "random-heuristic",
                key,
                (IndicatorSample(1, 0.2, 0.1), IndicatorSample(2, 0.4, 0.2)),
                exact=False,
            ),
            RunIndicatorTrack(
                "epsilon-constraint",
                configuration_key({}),
                (IndicatorSample(1, 0.9, 0.9),),
                exact=True,
            ),
        ]
    )

    assert is_exact_execution(1) is True
    assert is_exact_execution(5) is False
    assert is_exact_execution(5, catalog_exact=True) is True
    assert is_exact_execution(1, catalog_exact=False) is False
    assert len(curves) == 1
    assert curves[0].algorithm_id == "random-heuristic"
    assert curves[0].points[0].hypervolume == pytest.approx(0.2)


def test_different_parameters_remain_separate_curves() -> None:
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "random-heuristic",
                configuration_key({"iterations": 50, "seed": 3}),
                (IndicatorSample(1, 0.2, 0.1), IndicatorSample(2, 0.4, 0.2)),
                exact=False,
            ),
            RunIndicatorTrack(
                "random-heuristic",
                configuration_key({"iterations": 10, "seed": 4}),
                (IndicatorSample(1, 0.8, 0.4), IndicatorSample(2, 0.6, 0.3)),
                exact=False,
            ),
        ]
    )

    assert len(curves) == 2
    assert curves[0].points[0].hypervolume == pytest.approx(0.8)
    assert curves[1].points[0].hypervolume == pytest.approx(0.2)
