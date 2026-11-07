from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from optimization_problems.tsp.instance import TSPInstance


def _square_matrix(
    matrix: Sequence[Sequence[float]],
    name: str,
) -> tuple[tuple[float, ...], ...]:
    if isinstance(matrix, (str, bytes)):
        raise ValueError(f"{name} must be a square numeric matrix")

    try:
        raw_rows = tuple(matrix)
    except TypeError as error:
        raise ValueError(f"{name} must be a square numeric matrix") from error

    if any(isinstance(row, (str, bytes)) for row in raw_rows):
        raise ValueError(f"{name} must be a square numeric matrix")
    try:
        rows = tuple(tuple(row) for row in raw_rows)
    except TypeError as error:
        raise ValueError(f"{name} must be a square numeric matrix") from error

    size = len(rows)
    if size < 2 or any(isinstance(row, (str, bytes)) or len(row) != size for row in rows):
        raise ValueError(f"{name} must be a square matrix with at least two nodes")

    normalized_rows: list[tuple[float, ...]] = []
    for row_index, row in enumerate(rows):
        normalized_row: list[float] = []
        for column_index, value in enumerate(row):
            if isinstance(value, (bool, str, bytes)):
                raise ValueError(
                    f"{name}[{row_index}][{column_index}] must be a finite number"
                )
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(
                    f"{name}[{row_index}][{column_index}] must be a finite number"
                ) from error
            if not isfinite(number):
                raise ValueError(
                    f"{name}[{row_index}][{column_index}] must be a finite number"
                )
            normalized_row.append(number)
        normalized_rows.append(tuple(normalized_row))

    return tuple(normalized_rows)


def _validate_weight(weight: object) -> float:
    if isinstance(weight, bool):
        raise ValueError("weight must be a finite number in the interval [0, 1]")
    try:
        number = float(weight)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("weight must be a finite number in the interval [0, 1]") from error
    if not isfinite(number) or not 0 <= number <= 1:
        raise ValueError("weight must be a finite number in the interval [0, 1]")
    return number


def normalize_matrix(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    """Scale one cost matrix onto ``[0, 1]`` by min-max normalization.

    Each entry becomes ``(value - min) / (max - min)``, using the minimum and
    maximum of the whole matrix. A constant matrix has no relative variation
    and is mapped to zeros.
    """

    rows = _square_matrix(matrix, "matrix")
    lowest = min(value for row in rows for value in row)
    highest = max(value for row in rows for value in row)
    span = highest - lowest
    if span == 0:
        return tuple(tuple(0.0 for _ in row) for row in rows)

    normalized_rows: list[tuple[float, ...]] = []
    for row_index, row in enumerate(rows):
        normalized_row: list[float] = []
        for column_index, value in enumerate(row):
            number = (value - lowest) / span
            if not isfinite(number):
                raise ValueError(
                    f"matrix[{row_index}][{column_index}] overflowed during normalization"
                )
            normalized_row.append(number)
        normalized_rows.append(tuple(normalized_row))
    return tuple(normalized_rows)


def unify_costs(
    normalized_time: Sequence[Sequence[float]],
    normalized_distance: Sequence[Sequence[float]],
    weight: float,
) -> tuple[tuple[float, ...], ...]:
    """Combine normalized time and distance into one weighted cost matrix.

    ``s_ij(w) = w * t_hat_ij + (1 - w) * d_hat_ij``, with ``w`` in ``[0, 1]``.
    """

    chosen_weight = _validate_weight(weight)
    time = _unit_interval_matrix(normalized_time, "normalized_time")
    distance = _unit_interval_matrix(normalized_distance, "normalized_distance")
    if len(time) != len(distance):
        raise ValueError(
            "normalized_time and normalized_distance must have the same dimensions"
        )

    complement = 1.0 - chosen_weight
    return tuple(
        tuple(
            chosen_weight * time_cost + complement * distance_cost
            for time_cost, distance_cost in zip(time_row, distance_row, strict=True)
        )
        for time_row, distance_row in zip(time, distance, strict=True)
    )


def _unit_interval_matrix(
    matrix: Sequence[Sequence[float]],
    name: str,
) -> tuple[tuple[float, ...], ...]:
    rows = _square_matrix(matrix, name)
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            if not 0 <= value <= 1:
                raise ValueError(
                    f"{name}[{row_index}][{column_index}] must lie in the interval [0, 1]"
                )
    return rows


@dataclass(frozen=True)
class WeightedCostScalarization:
    """Normalized time and distance, and their weighted sum for one weight."""

    source: TSPInstance
    weight: float
    normalized_time: tuple[tuple[float, ...], ...]
    normalized_distance: tuple[tuple[float, ...], ...]
    cost_matrix: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source, TSPInstance):
            raise ValueError("source must be a TSPInstance")
        weight = _validate_weight(self.weight)
        object.__setattr__(self, "weight", weight)
        normalized_time = normalize_matrix(self.source.time_matrix)
        normalized_distance = normalize_matrix(self.source.distance_matrix)
        cost_matrix = unify_costs(normalized_time, normalized_distance, weight)
        if (
            self.normalized_time != normalized_time
            or self.normalized_distance != normalized_distance
            or self.cost_matrix != cost_matrix
        ):
            raise ValueError("cost matrix is not the weighted scalarization of source")

    @classmethod
    def scalarize(
        cls,
        instance: TSPInstance,
        weight: float,
    ) -> WeightedCostScalarization:
        """Normalize both objectives and unify them with ``weight``."""

        if not isinstance(instance, TSPInstance):
            raise ValueError("instance must be a TSPInstance")
        chosen_weight = _validate_weight(weight)
        normalized_time = normalize_matrix(instance.time_matrix)
        normalized_distance = normalize_matrix(instance.distance_matrix)
        return cls(
            source=instance,
            weight=chosen_weight,
            normalized_time=normalized_time,
            normalized_distance=normalized_distance,
            cost_matrix=unify_costs(
                normalized_time,
                normalized_distance,
                chosen_weight,
            ),
        )
