from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Literal, Sequence

ObjectiveDirection = Literal["minimize", "maximize"]


def non_dominated_mask(
    objective_values: Sequence[Sequence[Real]],
    directions: Sequence[ObjectiveDirection],
) -> tuple[bool, ...]:
    """Return whether each point is non-dominated under the given directions.

    Equal objective vectors do not dominate one another, so duplicate points
    are all retained in the returned mask.
    """
    normalized_directions = tuple(directions)
    if not normalized_directions or any(
        direction not in {"minimize", "maximize"}
        for direction in normalized_directions
    ):
        raise ValueError("directions must contain only 'minimize' or 'maximize'")

    points = tuple(
        _normalize_point(point, len(normalized_directions))
        for point in objective_values
    )
    mask: list[bool] = []
    for candidate_index, candidate in enumerate(points):
        is_dominated = any(
            _dominates(other, candidate, normalized_directions)
            for other_index, other in enumerate(points)
            if other_index != candidate_index
        )
        mask.append(not is_dominated)
    return tuple(mask)


def _normalize_point(point: Sequence[Real], dimension: int) -> tuple[float, ...]:
    if len(point) != dimension:
        raise ValueError("each objective vector must match the number of directions")

    normalized: list[float] = []
    for value in point:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("objective values must be finite real numbers")
        numeric_value = float(value)
        if not isfinite(numeric_value):
            raise ValueError("objective values must be finite real numbers")
        normalized.append(numeric_value)
    return tuple(normalized)


def _dominates(
    left: tuple[float, ...],
    right: tuple[float, ...],
    directions: tuple[ObjectiveDirection, ...],
) -> bool:
    no_worse = all(
        left_value <= right_value
        if direction == "minimize"
        else left_value >= right_value
        for left_value, right_value, direction in zip(left, right, directions)
    )
    strictly_better = any(
        left_value < right_value
        if direction == "minimize"
        else left_value > right_value
        for left_value, right_value, direction in zip(left, right, directions)
    )
    return no_worse and strictly_better
