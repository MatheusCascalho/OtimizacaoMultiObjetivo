"""Two-objective hypervolume of each mapped round.

The area follows ``docs/algorithms/hipervolume.md``: the union of the
axis-aligned rectangles between the candidate front and one reference
point. Objectives are normalized first, from 0 at the utopian point to 1
at the nadir. The reference is 1.1 times that normalized nadir, so a
positive range uses 1.1 and a null range stays 0.
The same reference is used for every round. The area is dimensionless.

The value is not stored. Callers compute it from the mapped sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from statistics import fmean, stdev
from typing import Mapping, Sequence

from multiobjective_algorithms.dominance import non_dominated_mask
from multiobjective_algorithms.reference_points import (
    ObjectiveSpec,
    ReferencePointError,
    estimate_reference_points,
    normalize_objectives,
)

REFERENCE_SHIFT = 1.1


@dataclass(frozen=True)
class RoundHypervolume:
    round_index: int
    hypervolume: float
    candidate_count: int
    distance_to_mean: float


@dataclass(frozen=True)
class HypervolumeSummary:
    nadir: tuple[float, ...]
    reference_point: tuple[float, ...]
    reference_shift: float
    rounds: tuple[RoundHypervolume, ...]
    mean_hypervolume: float
    sample_stdev_hypervolume: float
    coefficient_of_variation: float | None
    mean_candidate_count: float


def shift_reference_point(
    normalized_nadir: Sequence[float],
    shift: float = REFERENCE_SHIFT,
) -> tuple[float, ...]:
    """Multiply each normalized nadir component by ``shift``.

    The vector is already in minimization space: 0 is the utopian value and
    1 is the nadir when the range is positive, so the default factor 1.1
    places a positive range at 1.1. A component that stayed 0 because the
    utopian and nadir values coincide stays 0.
    """

    if not normalized_nadir:
        raise ValueError("o nadir normalizado precisa ter ao menos um objetivo")
    numeric_shift = _non_negative_finite(shift, "shift")
    return tuple(_finite_value(value) * numeric_shift for value in normalized_nadir)


def hypervolume_2d(
    points: Sequence[Sequence[float]],
    reference: Sequence[float],
) -> float:
    """Area dominated by a 2D front relative to ``reference``.

    ``points`` and ``reference`` are in normalized minimization space.
    Points that do not dominate the reference are ignored. An empty
    contribution is zero.
    """

    if len(reference) != 2:
        raise ValueError("o hipervolume em duas dimensões exige um ponto de referência com 2 objetivos")
    ref = (_finite_value(reference[0]), _finite_value(reference[1]))
    valid = [
        (_finite_value(point[0]), _finite_value(point[1]))
        for point in points
        if len(point) == 2 and point[0] <= ref[0] and point[1] <= ref[1]
    ]
    if not valid:
        return 0.0
    ordered = sorted(valid, key=lambda point: (point[0], -point[1]))
    total = 0.0
    last = len(ordered) - 1
    for index, point in enumerate(ordered):
        next_f1 = ref[0] if index == last else ordered[index + 1][0]
        width = next_f1 - point[0]
        height = ref[1] - point[1]
        if width > 0 and height > 0:
            total += width * height
    return total


def summarize_run_hypervolume(
    samples: Sequence[Mapping[str, object]],
    objectives: Sequence[ObjectiveSpec],
    *,
    shift: float = REFERENCE_SHIFT,
) -> HypervolumeSummary:
    """Hypervolume of each round's non-dominated front and the run aggregates.

    The nadir comes from the lexicographic estimate of the whole sample.
    Standard deviation is the sample standard deviation (n − 1). A single
    round has standard deviation 0. The coefficient of variation divides
    that deviation by the mean of every round. A mean of zero yields None.
    """

    specs = tuple(objectives)
    if len(specs) != 2 or len({spec.id for spec in specs}) != 2:
        raise ValueError("O hipervolume deste mapa exige exatamente 2 objetivos.")
    if not samples:
        raise ReferencePointError("Não há soluções mapeadas para calcular o hipervolume.")

    parsed = [_parse_sample(sample, specs) for sample in samples]
    reference = estimate_reference_points(
        [{spec.id: values[index] for index, spec in enumerate(specs)} for _, values in parsed],
        specs,
    )
    directions = [spec.direction for spec in specs]
    normalized_reference = shift_reference_point(
        normalize_objectives(reference.nadir, reference),
        shift,
    )

    grouped: dict[int, list[tuple[float, ...]]] = {}
    for round_index, values in parsed:
        grouped.setdefault(round_index, []).append(values)

    measured: list[tuple[int, float, int]] = []
    for round_index in sorted(grouped):
        points = grouped[round_index]
        mask = non_dominated_mask(points, directions)
        front = [point for point, keep in zip(points, mask) if keep]
        area = hypervolume_2d(
            [normalize_objectives(point, reference) for point in front],
            normalized_reference,
        )
        measured.append((round_index, area, len(front)))

    hypervolumes = [item[1] for item in measured]
    counts = [item[2] for item in measured]
    mean_hypervolume = fmean(hypervolumes)
    mean_count = fmean(counts)
    sample_stdev = 0.0 if len(hypervolumes) == 1 else stdev(hypervolumes)
    return HypervolumeSummary(
        nadir=reference.nadir,
        reference_point=normalized_reference,
        reference_shift=shift,
        rounds=tuple(
            RoundHypervolume(
                round_index=round_index,
                hypervolume=area,
                candidate_count=count,
                distance_to_mean=area - mean_hypervolume,
            )
            for round_index, area, count in measured
        ),
        mean_hypervolume=mean_hypervolume,
        sample_stdev_hypervolume=sample_stdev,
        coefficient_of_variation=coefficient_of_variation(mean_hypervolume, sample_stdev),
        mean_candidate_count=mean_count,
    )


def coefficient_of_variation(mean: float, sample_stdev: float) -> float | None:
    """Sample coefficient of variation, ``sample_stdev / mean``.

    The quotient is undefined when the mean is zero, so the result is None
    instead of a fabricated number.
    """

    if mean == 0:
        return None
    return sample_stdev / mean


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


def _non_negative_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a non-negative finite number")
    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be a non-negative finite number")
    return numeric_value
