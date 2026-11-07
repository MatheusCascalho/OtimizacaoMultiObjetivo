import pytest

from multiobjective_algorithms import (
    ObjectiveSpec,
    accumulated_prefix_sizes,
    aggregate_quality_evolution,
    configuration_key,
    estimate_reference_points,
    hypervolume_2d,
    is_exact_execution,
    measure_run_indicators,
    non_dominated_mask,
    normalize_objectives,
    shift_reference_point,
)
from multiobjective_algorithms.quality_evolution import (
    IndicatorSample,
    RunIndicatorTrack,
)

OBJECTIVES = (
    ObjectiveSpec("time", "minimize"),
    ObjectiveSpec("distance", "minimize"),
)


def _attempt(round_index: int, attempt: int, time: float, distance: float) -> dict:
    return {
        "round": round_index,
        "attempt": attempt,
        "time": time,
        "distance": distance,
    }


def _prefix_hypervolume(samples: list[dict], round_index: int, size: int) -> float:
    reference = estimate_reference_points(
        [{"time": sample["time"], "distance": sample["distance"]} for sample in samples],
        OBJECTIVES,
    )
    normalized_reference = shift_reference_point(normalize_objectives(reference.nadir, reference))
    ordered = sorted(
        (sample for sample in samples if sample["round"] == round_index),
        key=lambda sample: sample["attempt"],
    )[:size]
    points = [(sample["time"], sample["distance"]) for sample in ordered]
    mask = non_dominated_mask(points, ("minimize", "minimize"))
    front = [
        normalize_objectives(point, reference)
        for point, keep in zip(points, mask)
        if keep
    ]
    return hypervolume_2d(front, normalized_reference)


def test_prefix_lengths_follow_blocks_of_ten() -> None:
    assert accumulated_prefix_sizes(50) == [10, 20, 30, 40, 50]
    assert accumulated_prefix_sizes(25) == [10, 20, 25]
    assert accumulated_prefix_sizes(10) == [10]
    assert accumulated_prefix_sizes(7) == [7]
    assert accumulated_prefix_sizes(0) == []


def test_fifty_attempts_keep_every_tenth_and_two_rounds_stay_separate() -> None:
    samples = [
        _attempt(round_index, attempt, float(attempt + round_index), float(60 - attempt))
        for round_index in (1, 2)
        for attempt in range(1, 51)
    ]

    measured = measure_run_indicators(samples, OBJECTIVES)
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "neuro-lkh",
                configuration_key({"iterations": 50, "repetitions": 5, "seed": 1}),
                series.round_index,
                series.samples,
                exact=False,
            )
            for series in measured
        ]
    )

    assert [series.round_index for series in measured] == [1, 2]
    assert [item.accumulated_samples for item in measured[0].samples] == [10, 20, 30, 40, 50]
    assert [curve.round_index for curve in curves] == [1, 2]
    assert [point.accumulated_samples for point in curves[0].points] == [10, 20, 30, 40, 50]


def test_prefix_of_ten_excludes_the_eleventh_attempt_even_when_it_is_listed_first() -> None:
    first_ten = [
        _attempt(1, attempt, float(attempt), float(12 - attempt))
        for attempt in range(1, 11)
    ]
    eleventh = _attempt(1, 11, 3.0, 3.0)
    samples = [eleventh, *first_ten]

    measured = measure_run_indicators(samples, OBJECTIVES)

    assert [item.accumulated_samples for item in measured[0].samples] == [10, 11]
    assert measured[0].samples[0].hypervolume == pytest.approx(_prefix_hypervolume(samples, 1, 10))
    assert measured[0].samples[1].hypervolume == pytest.approx(_prefix_hypervolume(samples, 1, 11))
    assert measured[0].samples[0].hypervolume != pytest.approx(measured[0].samples[1].hypervolume)
    assert measured[0].samples[0].spread != pytest.approx(measured[0].samples[1].spread)


def test_prefix_uses_the_reference_of_the_whole_execution() -> None:
    round_one = [_attempt(1, attempt, float(attempt), float(12 - attempt)) for attempt in range(1, 11)]
    wider = round_one + [_attempt(2, 1, 0.0, 20.0), _attempt(2, 2, 20.0, 0.0)]

    alone = measure_run_indicators(round_one, OBJECTIVES)
    combined = measure_run_indicators(wider, OBJECTIVES)

    assert combined[0].samples[0].hypervolume == pytest.approx(_prefix_hypervolume(wider, 1, 10))
    assert combined[0].samples[0].hypervolume != pytest.approx(alone[0].samples[0].hypervolume)
    assert combined[0].samples[0].spread != pytest.approx(alone[0].samples[0].spread)


def test_a_missing_attempt_index_is_rejected() -> None:
    with pytest.raises(ValueError, match="attempt"):
        measure_run_indicators(
            [{"round": 1, "time": 1.0, "distance": 2.0}],
            OBJECTIVES,
        )


def test_mean_of_two_executions_at_the_same_round_and_prefix() -> None:
    key = configuration_key({"iterations": 50, "repetitions": 5, "seed": 1})
    assert key == configuration_key({"iterations": 50, "repetitions": 5, "seed": 99})
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "neuro-lkh",
                key,
                1,
                (IndicatorSample(10, 0.2, 0.1), IndicatorSample(20, 0.4, 0.3)),
                exact=False,
            ),
            RunIndicatorTrack(
                "neuro-lkh",
                key,
                1,
                (IndicatorSample(10, 0.4, 0.3), IndicatorSample(20, 0.8, 0.5)),
                exact=False,
            ),
            RunIndicatorTrack(
                "neuro-lkh",
                key,
                2,
                (IndicatorSample(10, 1.0, 0.2),),
                exact=False,
            ),
        ]
    )

    assert [curve.round_index for curve in curves] == [1, 2]
    assert curves[0].points[0].accumulated_samples == pytest.approx(10)
    assert curves[0].points[0].hypervolume == pytest.approx(0.3)
    assert curves[0].points[0].spread == pytest.approx(0.2)
    assert curves[0].points[1].hypervolume == pytest.approx(0.6)
    assert curves[1].points[0].hypervolume == pytest.approx(1.0)


def test_a_prefix_reached_by_only_one_execution_keeps_that_value() -> None:
    key = configuration_key({"iterations": 20})
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "random-heuristic",
                key,
                1,
                (IndicatorSample(10, 0.2, 0.4),),
                exact=False,
            ),
            RunIndicatorTrack(
                "random-heuristic",
                key,
                1,
                (IndicatorSample(10, 0.6, 0.8), IndicatorSample(20, 0.9, 0.1)),
                exact=False,
            ),
        ]
    )

    assert [point.accumulated_samples for point in curves[0].points] == [10, 20]
    assert curves[0].points[0].hypervolume == pytest.approx(0.4)
    assert curves[0].points[1].hypervolume == pytest.approx(0.9)


def test_an_exact_method_does_not_enter_the_curves() -> None:
    key = configuration_key({"iterations": 50})
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "random-heuristic",
                key,
                1,
                (IndicatorSample(10, 0.2, 0.1),),
                exact=False,
            ),
            RunIndicatorTrack(
                "epsilon-constraint",
                configuration_key({}),
                1,
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


def test_different_parameters_remain_separate_curves() -> None:
    curves = aggregate_quality_evolution(
        [
            RunIndicatorTrack(
                "random-heuristic",
                configuration_key({"iterations": 50, "seed": 3}),
                1,
                (IndicatorSample(10, 0.2, 0.1),),
                exact=False,
            ),
            RunIndicatorTrack(
                "random-heuristic",
                configuration_key({"iterations": 10, "seed": 4}),
                1,
                (IndicatorSample(10, 0.8, 0.4),),
                exact=False,
            ),
        ]
    )

    assert len(curves) == 2
    assert curves[0].points[0].hypervolume == pytest.approx(0.8)
    assert curves[1].points[0].hypervolume == pytest.approx(0.2)
