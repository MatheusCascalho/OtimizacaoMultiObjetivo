import unittest

from monoobjective_algorithms.interfaces import SolveRequest
from monoobjective_algorithms.tsp.heuristics import RandomHeuristic
from optimization_problems.tsp import TSPInstance


class RandomHeuristicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = TSPInstance(
            time_matrix=[
                [0, 2, 8, 4],
                [7, 0, 3, 5],
                [4, 6, 0, 9],
                [3, 2, 1, 0],
            ],
            distance_matrix=[
                [0, 5, 9, 3],
                [8, 0, 2, 7],
                [3, 7, 0, 6],
                [4, 5, 8, 0],
            ],
        )

    def test_returns_a_closed_hamiltonian_cycle_and_both_costs(self) -> None:
        result = RandomHeuristic(seed=19).solve(
            self.instance,
            SolveRequest(objective="time"),
        )

        self.assertEqual(result.status, "feasible")
        self.assertIsNotNone(result.solution)
        route = result.solution.route
        self.assertEqual(route[0], route[-1])
        self.assertEqual(route[0], 1)
        self.assertEqual(set(route[:-1]), {1, 2, 3, 4})
        self.assertEqual(len(route), self.instance.node_count + 1)
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

    def test_same_seed_produces_same_route(self) -> None:
        request = SolveRequest(objective="distance", parameters={"seed": 42})

        result_a = RandomHeuristic().solve(self.instance, request)
        result_b = RandomHeuristic().solve(self.instance, request)

        self.assertEqual(result_a.solution, result_b.solution)

    def test_supports_both_objectives_but_not_objective_limits(self) -> None:
        heuristic = RandomHeuristic(seed=5)

        for objective in ("time", "distance"):
            result = heuristic.solve(self.instance, SolveRequest(objective=objective))
            self.assertEqual(result.status, "feasible")

        with self.assertRaisesRegex(ValueError, "does not support objective limits"):
            heuristic.solve(
                self.instance,
                SolveRequest(objective="time", objective_limits={"distance": 10}),
            )

    def test_rejects_invalid_objective_or_parameters(self) -> None:
        heuristic = RandomHeuristic()

        with self.assertRaisesRegex(ValueError, "objective must"):
            heuristic.solve(self.instance, SolveRequest(objective="cost"))
        with self.assertRaisesRegex(ValueError, "unsupported RandomHeuristic parameter"):
            heuristic.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"unknown": True}),
            )
        with self.assertRaisesRegex(ValueError, "seed must"):
            heuristic.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"seed": "not-an-integer"}),
            )
        with self.assertRaisesRegex(ValueError, "seed must"):
            RandomHeuristic(seed=True)


if __name__ == "__main__":
    unittest.main()
