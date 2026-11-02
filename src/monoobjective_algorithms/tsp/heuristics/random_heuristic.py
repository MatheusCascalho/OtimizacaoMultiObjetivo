from __future__ import annotations

import random
from dataclasses import dataclass
from numbers import Integral

from monoobjective_algorithms.interfaces import (
    SolveRequest,
    SolveResult,
    SolverCapabilities,
)
from optimization_problems.tsp import TSPInstance

_TSP_OBJECTIVES = frozenset({"time", "distance"})


@dataclass(frozen=True)
class TSPSolution:
    """A closed Hamiltonian cycle, with node identifiers starting at 1."""

    route: tuple[int, ...]


class RandomHeuristic:
    """Return a uniformly sampled feasible TSP tour as a baseline."""

    algorithm_id = "random-heuristic"
    capabilities = SolverCapabilities(supports_objective_limits=False)

    def __init__(self, seed: int | None = None) -> None:
        self._validate_seed(seed)
        self._seed = seed
        self._random = random.Random(seed)

    def solve(
        self,
        instance: TSPInstance,
        request: SolveRequest,
    ) -> SolveResult[TSPSolution]:
        if request.objective not in _TSP_OBJECTIVES:
            raise ValueError("objective must be 'time' or 'distance'")
        if request.objective_limits:
            raise ValueError("RandomHeuristic does not support objective limits")

        unknown_parameters = set(request.parameters) - {"seed"}
        if unknown_parameters:
            names = ", ".join(sorted(unknown_parameters))
            raise ValueError(f"unsupported RandomHeuristic parameter(s): {names}")

        if "seed" in request.parameters:
            seed = request.parameters["seed"]
            self._validate_seed(seed)
            rng = random.Random(seed)
        else:
            rng = self._random

        nodes = list(range(2, instance.node_count + 1))
        rng.shuffle(nodes)
        route = (1, *nodes, 1)

        total_time = sum(
            instance.time_matrix[source - 1][target - 1]
            for source, target in zip(route, route[1:])
        )
        total_distance = sum(
            instance.distance_matrix[source - 1][target - 1]
            for source, target in zip(route, route[1:])
        )

        return SolveResult(
            status="feasible",
            solution=TSPSolution(route=route),
            objective_values={
                "time": total_time,
                "distance": total_distance,
            },
        )

    @staticmethod
    def _validate_seed(seed: object) -> None:
        if seed is not None and (
            isinstance(seed, bool) or not isinstance(seed, Integral)
        ):
            raise ValueError("seed must be an integer or None")
