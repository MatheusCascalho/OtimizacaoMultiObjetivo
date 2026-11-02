from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


def _normalize_matrix(
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


@dataclass(frozen=True)
class TSPInstance:
    """Directed TSP input with aligned time and distance cost matrices."""

    time_matrix: Sequence[Sequence[float]]
    distance_matrix: Sequence[Sequence[float]]

    def __post_init__(self) -> None:
        time_matrix = _normalize_matrix(self.time_matrix, "time_matrix")
        distance_matrix = _normalize_matrix(self.distance_matrix, "distance_matrix")
        if len(time_matrix) != len(distance_matrix):
            raise ValueError("time_matrix and distance_matrix must have the same dimensions")

        object.__setattr__(self, "time_matrix", time_matrix)
        object.__setattr__(self, "distance_matrix", distance_matrix)

    @property
    def node_count(self) -> int:
        return len(self.time_matrix)
