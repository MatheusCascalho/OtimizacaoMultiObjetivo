from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral
from typing import Sequence

from optimization_problems.tsp.instance import TSPInstance


def _off_diagonal_absolute_sum(matrix: Sequence[Sequence[float]]) -> float:
    total = 0.0
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            if row_index != column_index:
                total += abs(value)
    return total


def _separation_threshold(instance: TSPInstance) -> float:
    """Largest sum of absolute arc costs among the two objectives.

    A penalty strictly above this value makes every symmetric tour that is
    not the image of an asymmetric tour strictly worse on both objectives.
    """

    return max(
        _off_diagonal_absolute_sum(instance.time_matrix),
        _off_diagonal_absolute_sum(instance.distance_matrix),
    )


def _validate_penalty(penalty: object, minimum: float) -> float:
    if isinstance(penalty, bool):
        raise ValueError("penalty must be a finite number greater than the arc-cost threshold")
    try:
        number = float(penalty)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "penalty must be a finite number greater than the arc-cost threshold"
        ) from error
    if not isfinite(number) or number <= minimum:
        raise ValueError(
            "penalty must be a finite number greater than the arc-cost threshold"
        )
    return number


def _symmetrize_matrix(
    matrix: Sequence[Sequence[float]],
    penalty: float,
) -> tuple[tuple[float, ...], ...]:
    node_count = len(matrix)
    size = 2 * node_count
    rows = [[penalty] * size for _ in range(size)]
    for source in range(node_count):
        for target in range(node_count):
            cost = -penalty if source == target else matrix[source][target]
            rows[source][node_count + target] = cost
            rows[node_count + target][source] = cost
    return tuple(tuple(row) for row in rows)


def _symmetrized_instance(instance: TSPInstance, penalty: float) -> TSPInstance:
    return TSPInstance(
        time_matrix=_symmetrize_matrix(instance.time_matrix, penalty),
        distance_matrix=_symmetrize_matrix(instance.distance_matrix, penalty),
    )


def _as_node(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError("symmetric route nodes must be integers")
    return int(value)


def _closed_node_cycle(route: Sequence[int], node_count: int) -> tuple[int, ...]:
    if isinstance(route, (str, bytes)):
        raise ValueError(
            "symmetric route must be a Hamiltonian cycle on the symmetrized nodes"
        )
    try:
        nodes = tuple(_as_node(node) for node in route)
    except TypeError as error:
        raise ValueError(
            "symmetric route must be a Hamiltonian cycle on the symmetrized nodes"
        ) from error

    if len(nodes) == node_count + 1:
        if nodes[0] != nodes[-1]:
            raise ValueError(
                "symmetric route must be a Hamiltonian cycle on the symmetrized nodes"
            )
        nodes = nodes[:-1]
    if len(nodes) != node_count or set(nodes) != set(range(1, node_count + 1)):
        raise ValueError(
            "symmetric route must be a Hamiltonian cycle on the symmetrized nodes"
        )
    return nodes


def _split_node(node: int, source_node_count: int) -> tuple[int, str]:
    if node <= source_node_count:
        return node, "out"
    return node - source_node_count, "in"


@dataclass(frozen=True)
class JonkerVolgenantSymmetrization:
    """Symmetric 2n-node equivalent of an asymmetric TSP instance.

    Original city ``i`` (1-based) becomes departure node ``i`` and arrival
    node ``n + i``. In the doubled cost matrix, departure-to-arrival edges
    keep the original arc cost, each city is tied to itself by an edge of
    cost ``-penalty``, and every remaining entry is ``penalty``.

    The default penalty is one plus the larger sum of absolute off-diagonal
    costs. With that choice, every optimal symmetric tour uses all of the
    tying edges, and its cost is the asymmetric tour cost shifted by
    ``-n * penalty`` on both objectives.
    """

    source: TSPInstance
    instance: TSPInstance
    penalty: float

    def __post_init__(self) -> None:
        if not isinstance(self.source, TSPInstance):
            raise ValueError("source must be a TSPInstance")
        penalty = _validate_penalty(self.penalty, _separation_threshold(self.source))
        object.__setattr__(self, "penalty", penalty)
        if not isinstance(self.instance, TSPInstance):
            raise ValueError("instance must be a TSPInstance")
        if self.instance != _symmetrized_instance(self.source, penalty):
            raise ValueError(
                "instance is not the Jonker-Volgenant symmetrization of source"
            )

    @property
    def source_node_count(self) -> int:
        return self.source.node_count

    @classmethod
    def transform(
        cls,
        instance: TSPInstance,
        penalty: float | None = None,
    ) -> JonkerVolgenantSymmetrization:
        """Build the symmetric instance with 2n nodes."""

        if not isinstance(instance, TSPInstance):
            raise ValueError("instance must be a TSPInstance")
        threshold = _separation_threshold(instance)
        if penalty is None:
            chosen = threshold + 1.0
            if not isfinite(chosen) or chosen <= threshold:
                raise ValueError("penalty overflowed while symmetrizing the instance")
        else:
            chosen = _validate_penalty(penalty, threshold)
        return cls(
            source=instance,
            instance=_symmetrized_instance(instance, chosen),
            penalty=chosen,
        )

    def out_node(self, city: int) -> int:
        """1-based original city to its 1-based departure node."""

        self._validate_city(city)
        return city

    def in_node(self, city: int) -> int:
        """1-based original city to its 1-based arrival node."""

        self._validate_city(city)
        return self.source_node_count + city

    def original_route(self, symmetric_route: Sequence[int]) -> tuple[int, ...]:
        """Recover the closed asymmetric tour, starting and ending at city 1.

        ``symmetric_route`` is a Hamiltonian cycle on the doubled node set.
        It may repeat the first node at the end. Coupling edges are dropped,
        and each remaining edge is read as the original arc from its
        departure endpoint to its arrival endpoint.
        """

        node_count = self.source_node_count
        nodes = _closed_node_cycle(symmetric_route, 2 * node_count)
        successors: dict[int, int] = {}
        for start, end in zip(nodes, nodes[1:] + nodes[:1]):
            start_city, start_role = _split_node(start, node_count)
            end_city, end_role = _split_node(end, node_count)
            if start_role == end_role:
                raise ValueError("symmetric route uses a forbidden edge")
            if start_city == end_city:
                continue
            if start_role == "out":
                origin, destination = start_city, end_city
            else:
                origin, destination = end_city, start_city
            if origin in successors:
                raise ValueError("symmetric route does not encode one asymmetric tour")
            successors[origin] = destination

        if set(successors) != set(range(1, node_count + 1)):
            raise ValueError("symmetric route does not encode one asymmetric tour")

        route = [1]
        current = 1
        for _ in range(node_count - 1):
            current = successors[current]
            if current in route:
                raise ValueError("symmetric route does not encode one asymmetric tour")
            route.append(current)
        if successors[current] != 1:
            raise ValueError("symmetric route does not encode one asymmetric tour")
        route.append(1)
        return tuple(route)

    def restored_objective(self, symmetric_objective: float) -> float:
        """Remove the ``-n * penalty`` shift from one symmetric objective total."""

        if isinstance(symmetric_objective, bool):
            raise ValueError("symmetric objective must be a finite number")
        try:
            value = float(symmetric_objective)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("symmetric objective must be a finite number") from error
        if not isfinite(value):
            raise ValueError("symmetric objective must be a finite number")
        return value + self.source_node_count * self.penalty

    def _validate_city(self, city: object) -> None:
        if (
            isinstance(city, bool)
            or not isinstance(city, Integral)
            or not 1 <= int(city) <= self.source_node_count
        ):
            raise ValueError(
                f"city must be an integer from 1 to {self.source_node_count}"
            )
