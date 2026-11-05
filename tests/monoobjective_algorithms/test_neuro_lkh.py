import unittest

import numpy as np

from monoobjective_algorithms.interfaces import SolveRequest
from monoobjective_algorithms.tsp.heuristics import NeuroLKH
from monoobjective_algorithms.tsp.heuristics.neurolkh_costs import scale_symmetric_costs
from optimization_problems.tsp import (
    JonkerVolgenantSymmetrization,
    TSPInstance,
    WeightedCostScalarization,
)


class FakeBackend:
    def __init__(self, tour=(1, 5, 2, 6, 3, 4, 1), error: str | None = None) -> None:
        self.tour = tour
        self.error = error
        self.calls: list[dict[str, object]] = []

    def solve_symmetric(self, cost_matrix, *, trials, seed):
        self.calls.append(
            {"cost_matrix": cost_matrix, "trials": trials, "seed": seed}
        )
        if self.error is not None:
            raise RuntimeError(self.error)
        return self.tour


class NeuroLKHTests(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = TSPInstance(
            time_matrix=[
                [0, 10, 15],
                [20, 0, 5],
                [9, 12, 0],
            ],
            distance_matrix=[
                [0, 1, 4],
                [8, 0, 2],
                [3, 6, 0],
            ],
        )
        self.backend = FakeBackend()
        self.solver = NeuroLKH(seed=3, backend=self.backend)

    def _expected_matrix(self, weight: float):
        scalarized = WeightedCostScalarization.scalarize(self.instance, weight)
        unified = TSPInstance(
            time_matrix=scalarized.cost_matrix,
            distance_matrix=scalarized.cost_matrix,
        )
        return JonkerVolgenantSymmetrization.transform(unified).instance.time_matrix

    def test_backend_receives_the_symmetrized_unified_cost(self) -> None:
        result = self.solver.solve(
            self.instance,
            SolveRequest(objective="time", parameters={"weight": 0.25}),
        )

        self.assertEqual(
            self.backend.calls[0]["cost_matrix"],
            self._expected_matrix(0.25),
        )
        self.assertEqual(self.backend.calls[0]["trials"], 1000)
        self.assertEqual(self.backend.calls[0]["seed"], 3)
        self.assertEqual(result.status, "feasible")
        self.assertEqual(result.solution.route, (1, 2, 3, 1))
        route = result.solution.route
        self.assertEqual(route[0], route[-1])
        self.assertEqual(
            result.objective_values["time"],
            sum(
                self.instance.time_matrix[source - 1][target - 1]
                for source, target in zip(route, route[1:])
            ),
        )
        self.assertEqual(
            result.objective_values["distance"],
            sum(
                self.instance.distance_matrix[source - 1][target - 1]
                for source, target in zip(route, route[1:])
            ),
        )
        self.assertEqual(result.objective_values["time"], 10 + 5 + 9)
        self.assertEqual(result.objective_values["distance"], 1 + 2 + 3)

    def test_integer_scale_keeps_coupling_edges_strictly_cheaper(self) -> None:
        matrix = np.asarray(self._expected_matrix(0.5), dtype=float)
        scaled, details = scale_symmetric_costs(matrix)
        node_count = self.instance.node_count

        self.assertLessEqual(int(scaled.max()), 20_000_000)
        self.assertGreater(details["scale"], 0)
        for city in range(node_count):
            coupling = int(scaled[city, node_count + city])
            for other in range(node_count):
                if other == city:
                    continue
                self.assertLess(coupling, int(scaled[city, node_count + other]))

    def test_same_weight_and_seed_are_deterministic(self) -> None:
        request = SolveRequest(
            objective="distance",
            parameters={"weight": 0.3, "seed": 11, "lkh_trials": 5},
        )

        first = self.solver.solve(self.instance, request)
        second = NeuroLKH(backend=self.backend).solve(self.instance, request)

        self.assertEqual(first, second)
        self.assertEqual(self.backend.calls[0]["cost_matrix"], self.backend.calls[1]["cost_matrix"])
        self.assertEqual(self.backend.calls[0]["seed"], 11)
        self.assertEqual(self.backend.calls[0]["trials"], 5)

    def test_rejects_bad_objective_limits_and_parameters(self) -> None:
        for objective in ("time", "distance"):
            result = self.solver.solve(
                self.instance,
                SolveRequest(objective=objective, parameters={"weight": 0}),
            )
            self.assertEqual(result.status, "feasible")
        result = self.solver.solve(
            self.instance,
            SolveRequest(objective="time", parameters={"weight": 1}),
        )
        self.assertEqual(result.status, "feasible")

        with self.assertRaisesRegex(ValueError, "objective must"):
            self.solver.solve(self.instance, SolveRequest(objective="cost"))
        with self.assertRaisesRegex(ValueError, "does not support objective limits"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", objective_limits={"distance": 10}),
            )
        with self.assertRaisesRegex(ValueError, "unsupported NeuroLKH parameter"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"unknown": True}),
            )
        with self.assertRaisesRegex(ValueError, "weight must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"weight": -0.01}),
            )
        with self.assertRaisesRegex(ValueError, "weight must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"weight": 1.1}),
            )
        with self.assertRaisesRegex(ValueError, "weight must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"weight": True}),
            )
        with self.assertRaisesRegex(ValueError, "seed must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"seed": "not-an-integer"}),
            )
        with self.assertRaisesRegex(ValueError, "seed must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"seed": True}),
            )
        with self.assertRaisesRegex(ValueError, "seed must"):
            NeuroLKH(seed=True, backend=self.backend)
        with self.assertRaisesRegex(ValueError, "lkh_trials must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"lkh_trials": 0}),
            )
        with self.assertRaisesRegex(ValueError, "lkh_trials must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"lkh_trials": -4}),
            )
        with self.assertRaisesRegex(ValueError, "lkh_trials must"):
            self.solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"lkh_trials": 1.5}),
            )
        with self.assertRaisesRegex(ValueError, "lkh_trials must"):
            NeuroLKH(lkh_trials=True, backend=self.backend)

    def test_backend_failure_does_not_fabricate_a_tour(self) -> None:
        failed = NeuroLKH(backend=FakeBackend(error="extension missing"))
        result = failed.solve(self.instance, SolveRequest(objective="time"))

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.solution)
        self.assertEqual(result.objective_values, {})

        undecodable = NeuroLKH(backend=FakeBackend(tour=(1, 2, 3, 4, 5, 6)))
        result = undecodable.solve(self.instance, SolveRequest(objective="distance"))

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.solution)
        self.assertEqual(result.objective_values, {})


if __name__ == "__main__":
    unittest.main()
