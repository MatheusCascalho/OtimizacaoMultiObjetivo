"""Deb's spread metric (Δ) for each mapped two-objective front.

The definition follows ``docs/algorithms/espalhamento_delta.md``. Consecutive
distances are the ``|A| - 1`` Euclidean gaps of the front ordered by the
first objective, matching the calculation steps and the Python example in
that document. Objectives are normalized first, from 0 at the utopian point
to 1 at the nadir, with the same rule used by the hypervolume. The reference
extremes are the best value of each objective in the union of every round,
because the mapped sample has no analytical Pareto front.

Δ is 0 when the gaps are equal and the front reaches both extremes. A front
with fewer than two solutions has no consecutive gap and yields 1. The value
is not stored. Callers compute it from the mapped sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import dist, isfinite
from numbers import Real
from statistics import fmean, stdev
from typing import Mapping, Sequence

from multiobjective_algorithms.dominance import non_dominated_mask
from multiobjective_algorithms.hypervolume import coefficient_of_variation
from multiobjective_algorithms.reference_points import (
    ObjectiveSpec,
    ReferencePointError,
    estimate_reference_points,
    normalize_objectives,
)

_DENOMINATOR_EPSILON = 1e-12


@dataclass(frozen=True)
class RoundSpread:
    round_index: int
    spread: float
    candidate_count: int


@dataclass(frozen=True)
class SpreadSummary:
    rounds: tuple[RoundSpread, ...]
    mean_spread: float
    sample_stdev_spread: float
    coefficient_of_variation: float | None


def spread_delta(
    front: Sequence[Sequence[float]],
    extremes: Sequence[Sequence[float]],
) -> float:
    """Δ of one normalized front against the two reference extremes.

    ``front`` holds points ``(f1, f2)`` already in minimization space.
    ``extremes`` is ``(extreme of smallest f1, extreme of smallest f2)``.
    Fewer than two points returns 1. A denominator that collapses to zero
    returns 0, the uniform case in which every gap and both extreme
    distances are zero.
    """

    if len(extremes) != 2 or any(len(point) != 2 for point in extremes):
        raise ValueError("o espalhamento em duas dimensões exige dois extremos de referência")
    points = [_pair(point) for point in front]
    if len(points) < 2:
        return 1.0
    ordered = sorted(points, key=lambda point: (point[0], point[1]))
    distances = [
        dist(ordered[index], ordered[index + 1])
        for index in range(len(ordered) - 1)
    ]
    mean_distance = fmean(distances)
    extreme_f1 = _pair(extremes[0])
    extreme_f2 = _pair(extremes[1])
    extreme_distance = dist(ordered[0], extreme_f1) + dist(ordered[-1], extreme_f2)
    numerator = extreme_distance + sum(abs(distance - mean_distance) for distance in distances)
    denominator = extreme_distance + len(distances) * mean_distance
    if denominator <= _DENOMINATOR_EPSILON:
        return 0.0
    return numerator / denominator


def summarize_run_spread(
    samples: Sequence[Mapping[str, object]],
    objectives: Sequence[ObjectiveSpec],
) -> SpreadSummary:
    """Δ of each round's non-dominated front and the run aggregates.

    Standard deviation is the sample standard deviation (n − 1). A single
    round has standard deviation 0. The coefficient of variation divides
    that deviation by the mean of every round. A mean of zero yields None.
    """

    specs = tuple(objectives)
    if len(specs) != 2 or len({spec.id for spec in specs}) != 2:
        raise ValueError("O espalhamento deste mapa exige exatamente 2 objetivos.")
    if not samples:
        raise ReferencePointError("Não há soluções mapeadas para calcular o espalhamento.")

    parsed = [_parse_sample(sample, specs) for sample in samples]
    reference = estimate_reference_points(
        [{spec.id: values[index] for index, spec in enumerate(specs)} for _, values in parsed],
        specs,
    )
    directions = [spec.direction for spec in specs]
    extremes = _reference_extremes(
        [normalize_objectives(values, reference) for _, values in parsed]
    )

    grouped: dict[int, list[tuple[float, ...]]] = {}
    for round_index, values in parsed:
        grouped.setdefault(round_index, []).append(values)

    measured: list[RoundSpread] = []
    for round_index in sorted(grouped):
        points = grouped[round_index]
        mask = non_dominated_mask(points, directions)
        front = [
            normalize_objectives(point, reference)
            for point, keep in zip(points, mask)
            if keep
        ]
        measured.append(
            RoundSpread(
                round_index=round_index,
                spread=spread_delta(front, extremes),
                candidate_count=len(front),
            )
        )

    spreads = [item.spread for item in measured]
    sample_stdev = 0.0 if len(spreads) == 1 else stdev(spreads)
    mean_spread = fmean(spreads)
    return SpreadSummary(
        rounds=tuple(measured),
        mean_spread=mean_spread,
        sample_stdev_spread=sample_stdev,
        coefficient_of_variation=coefficient_of_variation(mean_spread, sample_stdev),
    )


def _reference_extremes(
    points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    extreme_f1 = min(points, key=lambda point: (point[0], point[1]))
    extreme_f2 = min(points, key=lambda point: (point[1], point[0]))
    return extreme_f1, extreme_f2


def _pair(point: Sequence[float]) -> tuple[float, float]:
    if len(point) != 2:
        raise ValueError("o espalhamento em duas dimensões exige pontos com 2 objetivos")
    return (_finite_value(point[0]), _finite_value(point[1]))


def _parse_sample(
    sample: Mapping[str, object],
    specs: Sequence[ObjectiveSpec],
) -> tuple[int, tuple[float, ...]]:
    round_index = sample.get("round")
    if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 1:
        raise ValueError("round must be an integer starting at 1")
    try:
        return round_index, tuple(_finite_value(sample[spec.id]) for spec in specs)
    except KeyError as error:
        raise ValueError("Os objetivos da execução não coincidem com o catálogo do problema.") from error


def _finite_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("objective values must be finite real numbers")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError("objective values must be finite real numbers")
    return numeric_value
