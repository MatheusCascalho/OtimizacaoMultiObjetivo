"""Evolution of hypervolume and spread inside each sampling round.

Each point is the candidate frontier of an accumulated prefix of that round:
the first 10 attempts, then the first 20, and so on. The last point is the
full round. A round with fewer than 10 attempts has a single point, at its
total. The utopian point, the nadir and the spread extremes belong to the
whole execution and stay fixed for every prefix. Dominance is recomputed on
the prefix; a dominance flag stored at the end of the round is not used.

Attempts without a persisted order are not part of this series. Callers must
not invent that order from solution identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import fmean
from typing import Mapping, Sequence

from multiobjective_algorithms.dominance import non_dominated_mask
from multiobjective_algorithms.hypervolume import (
    hypervolume_2d,
    shift_reference_point,
)
from multiobjective_algorithms.reference_points import (
    ObjectiveSpec,
    ReferencePointError,
    estimate_reference_points,
    normalize_objectives,
)
from multiobjective_algorithms.spread import spread_delta

PREFIX_STEP = 10
ACCUMULATED_SAMPLES_AXIS = "accumulated_samples"


@dataclass(frozen=True)
class IndicatorSample:
    accumulated_samples: int
    hypervolume: float
    spread: float


@dataclass(frozen=True)
class RoundIndicatorSeries:
    round_index: int
    samples: tuple[IndicatorSample, ...]


@dataclass(frozen=True)
class RunIndicatorTrack:
    algorithm_id: str
    configuration: tuple[tuple[str, object], ...]
    round_index: int
    samples: tuple[IndicatorSample, ...]
    exact: bool


@dataclass(frozen=True)
class MeanPoint:
    accumulated_samples: float
    hypervolume: float
    spread: float


@dataclass(frozen=True)
class MeanCurve:
    algorithm_id: str
    configuration: tuple[tuple[str, object], ...]
    round_index: int
    points: tuple[MeanPoint, ...]


def accumulated_prefix_sizes(total: int, step: int = PREFIX_STEP) -> list[int]:
    """Prefix lengths of one round, in blocks of ``step`` attempts.

    A total below ``step`` is a single prefix of that total. Otherwise the
    lengths are ``step, 2 * step, ...`` and the full total when it is not a
    multiple of ``step``.
    """

    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError("total must be a non-negative integer")
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise ValueError("step must be a positive integer")
    if total == 0:
        return []
    if total < step:
        return [total]
    sizes = list(range(step, total + 1, step))
    if sizes[-1] != total:
        sizes.append(total)
    return sizes


def is_exact_execution(distinct_rounds: int, catalog_exact: bool | None = None) -> bool:
    """Whether this execution stays out of the evolution curves.

    A catalog flag wins when it is present. Without one, a single delivered
    frontier is treated as exact and several rounds are treated as non-exact.
    """

    if isinstance(distinct_rounds, bool) or not isinstance(distinct_rounds, int) or distinct_rounds < 0:
        raise ValueError("distinct_rounds must be a non-negative integer")
    if catalog_exact is True:
        return True
    if catalog_exact is False:
        return False
    return distinct_rounds <= 1


def configuration_key(parameters: Mapping[str, object] | None) -> tuple[tuple[str, object], ...]:
    """Parameters that distinguish a curve, ignoring the repetition seed."""

    raw = dict(parameters or {})
    raw.pop("seed", None)
    return tuple(sorted((str(key), _freeze(value)) for key, value in raw.items()))


def measure_run_indicators(
    samples: Sequence[Mapping[str, object]],
    objectives: Sequence[ObjectiveSpec],
    step: int = PREFIX_STEP,
) -> tuple[RoundIndicatorSeries, ...]:
    """Hypervolume and Δ of each accumulated prefix, one series per round.

    ``samples`` are individual attempts. Each one needs ``round``, ``attempt``
    starting at 1, and the objective values. Attempts are ordered by that
    index. A missing attempt is rejected instead of using the sequence order.
    The reference and the spread extremes come from every attempt of the
    execution.
    """

    specs = tuple(objectives)
    if len(specs) != 2 or len({spec.id for spec in specs}) != 2:
        raise ValueError("A evolução deste mapa exige exatamente 2 objetivos.")
    if not samples:
        raise ReferencePointError("Não há amostragens mapeadas para calcular a evolução.")

    parsed = [_parse_attempt(sample, specs) for sample in samples]
    seen: set[tuple[int, int]] = set()
    for round_index, attempt, _values in parsed:
        key = (round_index, attempt)
        if key in seen:
            raise ValueError("attempt must be unique inside the round")
        seen.add(key)

    reference = estimate_reference_points(
        [{spec.id: values[index] for index, spec in enumerate(specs)} for _, _, values in parsed],
        specs,
    )
    directions = [spec.direction for spec in specs]
    normalized_reference = shift_reference_point(normalize_objectives(reference.nadir, reference))
    extremes = _execution_extremes(
        [normalize_objectives(values, reference) for _, _, values in parsed]
    )

    grouped: dict[int, list[tuple[int, tuple[float, ...]]]] = {}
    for round_index, attempt, values in parsed:
        grouped.setdefault(round_index, []).append((attempt, values))

    series: list[RoundIndicatorSeries] = []
    for round_index in sorted(grouped):
        ordered = [values for _attempt, values in sorted(grouped[round_index], key=lambda item: item[0])]
        measured: list[IndicatorSample] = []
        for size in accumulated_prefix_sizes(len(ordered), step):
            prefix = ordered[:size]
            mask = non_dominated_mask(prefix, directions)
            front = [
                normalize_objectives(point, reference)
                for point, keep in zip(prefix, mask)
                if keep
            ]
            measured.append(
                IndicatorSample(
                    accumulated_samples=size,
                    hypervolume=hypervolume_2d(front, normalized_reference),
                    spread=spread_delta(front, extremes),
                )
            )
        series.append(RoundIndicatorSeries(round_index, tuple(measured)))
    return tuple(series)


def aggregate_quality_evolution(tracks: Sequence[RunIndicatorTrack]) -> tuple[MeanCurve, ...]:
    """Mean indicator of comparable executions at the same round and prefix.

    Tracks marked exact are omitted. Executions share a curve when they use
    the same algorithm and the same parameters, ignoring the seed, and the
    mean is taken only at a shared round and prefix length. A prefix that
    only one execution reached keeps that execution's value. One execution
    therefore produces its own curves, one per round.
    """

    grouped: dict[tuple[str, tuple[tuple[str, object], ...], int], list[RunIndicatorTrack]] = {}
    for track in tracks:
        if track.exact or not track.samples:
            continue
        grouped.setdefault((track.algorithm_id, track.configuration, track.round_index), []).append(track)

    curves: list[MeanCurve] = []
    for algorithm_id, configuration, round_index in sorted(
        grouped,
        key=lambda item: (item[0], repr(item[1]), item[2]),
    ):
        buckets: dict[int, list[IndicatorSample]] = {}
        for member in grouped[(algorithm_id, configuration, round_index)]:
            for sample in member.samples:
                buckets.setdefault(sample.accumulated_samples, []).append(sample)
        points = tuple(
            MeanPoint(
                accumulated_samples=size,
                hypervolume=fmean(sample.hypervolume for sample in buckets[size]),
                spread=fmean(sample.spread for sample in buckets[size]),
            )
            for size in sorted(buckets)
        )
        curves.append(MeanCurve(algorithm_id, configuration, round_index, points))
    return tuple(curves)


def stable_number(value: float) -> int | float:
    """Emit an integer when the mean landed on a whole number of samples."""

    numeric = float(value)
    nearest = round(numeric)
    if abs(numeric - nearest) <= 1e-9:
        return int(nearest)
    return numeric


def _parse_attempt(
    sample: Mapping[str, object],
    specs: Sequence[ObjectiveSpec],
) -> tuple[int, int, tuple[float, ...]]:
    round_index = sample.get("round")
    attempt = sample.get("attempt")
    if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 1:
        raise ValueError("round must be an integer starting at 1")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt must be an integer starting at 1")
    try:
        values = tuple(_finite_objective(sample[spec.id]) for spec in specs)
    except KeyError as error:
        raise ValueError("Os objetivos da execução não coincidem com o catálogo do problema.") from error
    return round_index, attempt, values


def _finite_objective(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("objective values must be finite real numbers")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError("objective values must be finite real numbers")
    return numeric


def _execution_extremes(
    points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Best normalized point of each objective, matching the Δ reference.

    The first extreme minimizes the first objective; the second minimizes the
    second. Ties keep the other objective smaller, as in the run-level Δ.
    """

    extreme_f1 = min(points, key=lambda point: (point[0], point[1]))
    extreme_f2 = min(points, key=lambda point: (point[1], point[0]))
    return extreme_f1, extreme_f2


def _freeze(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    return str(value)
