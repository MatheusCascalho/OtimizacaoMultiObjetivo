"""Evolution of hypervolume and spread along a non-exact run.

The mapped sample stores one candidate frontier per ``round``. Attempt-level
frontiers and per-evaluation snapshots are not persisted, so the round index
is the iteration axis. Both indicators reuse the run-level utopian point and
nadir already used by the final hypervolume: each instant is normalized with
that same reference, not with the nadir of the instant itself.

Up to ten moments are kept. They are the iterations nearest to
``k * total / 10`` for ``k = 1..10``, with halves rounding toward the larger
index. A run with fewer than ten iterations keeps every existing iteration.
An exact method is one the catalog marks as exact, or, when the catalog is
silent, a run that delivers a single frontier.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Mapping, Sequence

from multiobjective_algorithms.hypervolume import summarize_run_hypervolume
from multiobjective_algorithms.reference_points import ObjectiveSpec
from multiobjective_algorithms.spread import summarize_run_spread

MOMENT_COUNT = 10
ITERATION_AXIS = "iteration"


@dataclass(frozen=True)
class IndicatorSample:
    iteration: int
    hypervolume: float
    spread: float


@dataclass(frozen=True)
class RunIndicatorTrack:
    algorithm_id: str
    configuration: tuple[tuple[str, object], ...]
    samples: tuple[IndicatorSample, ...]
    exact: bool


@dataclass(frozen=True)
class MeanPoint:
    iteration: float
    hypervolume: float
    spread: float


@dataclass(frozen=True)
class MeanCurve:
    algorithm_id: str
    configuration: tuple[tuple[str, object], ...]
    points: tuple[MeanPoint, ...]


def sample_iteration_indices(total: int, moments: int = MOMENT_COUNT) -> list[int]:
    """Return 1-based positions equally spaced from the first fraction through the end.

    ``total`` below ``moments`` yields ``1..total`` and does not invent
    positions. Otherwise each position is the integer nearest to
    ``step * total / moments``, and a tie rounds toward the larger index.
    """

    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError("total must be a non-negative integer")
    if isinstance(moments, bool) or not isinstance(moments, int) or moments < 1:
        raise ValueError("moments must be a positive integer")
    if total == 0:
        return []
    if total <= moments:
        return list(range(1, total + 1))

    used: set[int] = set()
    chosen: list[int] = []
    for step in range(1, moments + 1):
        index = (2 * step * total + moments) // (2 * moments)
        index = min(total, max(1, index))
        if index in used:
            index = _nearest_free_index(index, used, total)
        used.add(index)
        chosen.append(index)
    return chosen


def select_iteration_moments(
    iterations: Sequence[int],
    moments: int = MOMENT_COUNT,
) -> list[int]:
    """Pick up to ``moments`` iteration labels from the values that exist.

    Labels are the stored round indices. Positions come from
    :func:`sample_iteration_indices` over the sorted unique labels, so a
    contiguous run of 100 iterations is sampled at 10, 20, …, 100.
    """

    ordered = sorted(_valid_iterations(iterations))
    positions = sample_iteration_indices(len(ordered), moments)
    return [ordered[position - 1] for position in positions]


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
    moments: int = MOMENT_COUNT,
) -> tuple[IndicatorSample, ...]:
    """Hypervolume and Δ at the sampled rounds of one execution.

    Both summaries see the whole sample, so the utopian point, the nadir and
    the spread extremes belong to the execution rather than to each instant.
    """

    hypervolume = summarize_run_hypervolume(samples, objectives)
    spread = summarize_run_spread(samples, objectives)
    area_by_round = {item.round_index: item.hypervolume for item in hypervolume.rounds}
    spread_by_round = {item.round_index: item.spread for item in spread.rounds}
    if set(area_by_round) != set(spread_by_round):
        raise ValueError("hipervolume e espalhamento divergiram nas rodadas")
    selected = select_iteration_moments(tuple(area_by_round), moments)
    return tuple(
        IndicatorSample(
            iteration=iteration,
            hypervolume=area_by_round[iteration],
            spread=spread_by_round[iteration],
        )
        for iteration in selected
    )


def aggregate_quality_evolution(tracks: Sequence[RunIndicatorTrack]) -> tuple[MeanCurve, ...]:
    """Mean indicator at each aligned tenth of comparable executions.

    Tracks marked exact are omitted. Sample ``k`` of an execution that kept
    ``m`` moments stands for the fraction ``k / m`` and joins the tenth
    nearest to that fraction. A tie goes to the later tenth. The point's
    iteration is the mean of the iteration labels in that tenth, and each
    indicator is the mean of the values. A tenth that no execution reached
    is omitted, so a short execution does not invent moments. Two executions
    sampled in ten moments therefore line up 1st-with-1st through 10th-with-10th,
    and the last moment of a shorter execution lines up with the last tenth.
    """

    grouped: dict[tuple[str, tuple[tuple[str, object], ...]], list[RunIndicatorTrack]] = {}
    for track in tracks:
        if track.exact or not track.samples:
            continue
        grouped.setdefault((track.algorithm_id, track.configuration), []).append(track)

    curves: list[MeanCurve] = []
    for algorithm_id, configuration in sorted(grouped, key=lambda item: (item[0], repr(item[1]))):
        members = grouped[(algorithm_id, configuration)]
        buckets: dict[int, list[IndicatorSample]] = {slot: [] for slot in range(1, MOMENT_COUNT + 1)}
        for member in members:
            used: set[int] = set()
            count = len(member.samples)
            for index, sample in enumerate(member.samples, start=1):
                slot = _fraction_slot(index, count, MOMENT_COUNT)
                if slot in used:
                    slot = _nearest_free_index(slot, used, MOMENT_COUNT)
                used.add(slot)
                buckets[slot].append(sample)
        points = [
            MeanPoint(
                iteration=fmean(sample.iteration for sample in buckets[slot]),
                hypervolume=fmean(sample.hypervolume for sample in buckets[slot]),
                spread=fmean(sample.spread for sample in buckets[slot]),
            )
            for slot in range(1, MOMENT_COUNT + 1)
            if buckets[slot]
        ]
        curves.append(MeanCurve(algorithm_id, configuration, tuple(points)))
    return tuple(curves)


def stable_number(value: float) -> int | float:
    """Emit an integer when the mean landed on a whole iteration."""

    numeric = float(value)
    nearest = round(numeric)
    if abs(numeric - nearest) <= 1e-9:
        return int(nearest)
    return numeric


def _valid_iterations(iterations: Sequence[int]) -> set[int]:
    valid: set[int] = set()
    for iteration in iterations:
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
            raise ValueError("iteration must be an integer starting at 1")
        valid.add(iteration)
    return valid


def _fraction_slot(index: int, count: int, moments: int) -> int:
    """1-based tenth nearest to ``index / count``. Ties move to the later tenth."""

    if count == moments:
        return index
    slot = (2 * index * moments + count) // (2 * count)
    return min(moments, max(1, slot))


def _nearest_free_index(index: int, used: set[int], total: int) -> int:
    for distance in range(1, total + 1):
        higher = index + distance
        lower = index - distance
        if higher <= total and higher not in used:
            return higher
        if lower >= 1 and lower not in used:
            return lower
    raise ValueError("não há instante livre para amostrar")


def _freeze(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    return str(value)
