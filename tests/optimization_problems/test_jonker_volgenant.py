import itertools
import unittest

from optimization_problems.tsp import JonkerVolgenantSymmetrization, TSPInstance


class JonkerVolgenantSymmetrizationTests(unittest.TestCase):
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

    def test_builds_the_doubled_symmetric_blocks(self) -> None:
        penalty = 1_000_000.0
        symmetrized = JonkerVolgenantSymmetrization.transform(self.instance, penalty)
        time = symmetrized.instance.time_matrix
        distance = symmetrized.instance.distance_matrix

        self.assertEqual(symmetrized.penalty, penalty)
        self.assertEqual(symmetrized.source_node_count, 3)
        self.assertEqual(symmetrized.instance.node_count, 6)
        self.assertEqual(
            time,
            (
                (penalty, penalty, penalty, -penalty, 10, 15),
                (penalty, penalty, penalty, 20, -penalty, 5),
                (penalty, penalty, penalty, 9, 12, -penalty),
                (-penalty, 20, 9, penalty, penalty, penalty),
                (10, -penalty, 12, penalty, penalty, penalty),
                (15, 5, -penalty, penalty, penalty, penalty),
            ),
        )
        self.assertEqual(distance[0][4], 1)
        self.assertEqual(distance[4][0], 1)
        self.assertEqual(distance[1][3], 8)
        self.assertEqual(distance[2][4], 6)
        self.assertEqual(distance[0][3], -penalty)
        for matrix in (time, distance):
            for row in range(6):
                for column in range(6):
                    self.assertEqual(matrix[row][column], matrix[column][row])

    def test_default_penalty_exceeds_both_absolute_arc_sums(self) -> None:
        symmetrized = JonkerVolgenantSymmetrization.transform(self.instance)

        time_sum = 10 + 15 + 20 + 5 + 9 + 12
        distance_sum = 1 + 4 + 8 + 2 + 3 + 6
        self.assertEqual(symmetrized.penalty, max(time_sum, distance_sum) + 1)
        self.assertEqual(symmetrized.instance.time_matrix[0][1], symmetrized.penalty)
        self.assertEqual(
            symmetrized.instance.distance_matrix[0][3],
            -symmetrized.penalty,
        )

    def test_uses_penalty_on_the_coupling_edge_when_the_diagonal_is_nonzero(self) -> None:
        instance = TSPInstance(
            time_matrix=[[7, 10], [20, 9]],
            distance_matrix=[[4, 1], [3, 8]],
        )
        symmetrized = JonkerVolgenantSymmetrization.transform(instance, penalty=100)

        self.assertEqual(symmetrized.instance.time_matrix[0][2], -100)
        self.assertEqual(symmetrized.instance.time_matrix[1][3], -100)
        self.assertEqual(symmetrized.out_node(2), 2)
        self.assertEqual(symmetrized.in_node(2), 4)

    def test_recovers_the_asymmetric_tour_from_either_direction(self) -> None:
        symmetrized = JonkerVolgenantSymmetrization.transform(self.instance, penalty=1e6)
        forward = (1, 5, 2, 6, 3, 4, 1)
        reverse = (1, 4, 3, 6, 2, 5, 1)
        rotated = (5, 2, 6, 3, 4, 1, 5)
        open_route = (1, 5, 2, 6, 3, 4)

        self.assertEqual(symmetrized.original_route(forward), (1, 2, 3, 1))
        self.assertEqual(symmetrized.original_route(reverse), (1, 2, 3, 1))
        self.assertEqual(symmetrized.original_route(rotated), (1, 2, 3, 1))
        self.assertEqual(symmetrized.original_route(open_route), (1, 2, 3, 1))
        self.assertEqual(
            symmetrized.restored_objective(self._route_cost(forward, symmetrized, "time")),
            10 + 5 + 9,
        )
        self.assertEqual(
            symmetrized.restored_objective(
                self._route_cost(forward, symmetrized, "distance")
            ),
            1 + 2 + 3,
        )

    def test_default_penalty_separates_asymmetric_tours_from_other_cycles(self) -> None:
        instance = TSPInstance(
            time_matrix=[
                [0, -5, 4],
                [8, 0, 1],
                [3, -2, 0],
            ],
            distance_matrix=[
                [0, 9, 1],
                [-4, 0, 7],
                [2, 5, 0],
            ],
        )
        symmetrized = JonkerVolgenantSymmetrization.transform(instance)
        accepted: list[tuple[float, float]] = []
        rejected: list[tuple[float, float]] = []
        for perm in itertools.permutations(range(2, 7)):
            route = (1,) + perm + (1,)
            totals = (
                self._route_cost(route, symmetrized, "time"),
                self._route_cost(route, symmetrized, "distance"),
            )
            try:
                original = symmetrized.original_route(route)
            except ValueError:
                rejected.append(totals)
                continue
            self.assertEqual(
                symmetrized.restored_objective(totals[0]),
                self._original_cost(original, instance, "time"),
            )
            self.assertEqual(
                symmetrized.restored_objective(totals[1]),
                self._original_cost(original, instance, "distance"),
            )
            accepted.append(totals)

        self.assertTrue(accepted)
        self.assertTrue(rejected)
        best_time = min(total[0] for total in accepted)
        best_distance = min(total[1] for total in accepted)
        for time, distance in rejected:
            self.assertGreater(time, best_time)
            self.assertGreater(distance, best_distance)

    def test_rejects_routes_that_are_not_asymmetric_tours(self) -> None:
        symmetrized = JonkerVolgenantSymmetrization.transform(self.instance, penalty=1e6)

        with self.assertRaisesRegex(ValueError, "Hamiltonian cycle"):
            symmetrized.original_route((1, 5, 2, 6, 3, 1))
        with self.assertRaisesRegex(ValueError, "forbidden edge"):
            symmetrized.original_route((1, 2, 6, 3, 4, 5, 1))
        with self.assertRaisesRegex(ValueError, "one asymmetric tour"):
            symmetrized.original_route((1, 5, 3, 6, 2, 4, 1))
        with self.assertRaisesRegex(ValueError, "integers"):
            symmetrized.original_route((1, 5, 2, 6, 3, True))

    def test_rejects_penalties_that_do_not_separate_tours(self) -> None:
        threshold = 10 + 15 + 20 + 5 + 9 + 12
        with self.assertRaisesRegex(ValueError, "penalty"):
            JonkerVolgenantSymmetrization.transform(self.instance, penalty=threshold)
        with self.assertRaisesRegex(ValueError, "penalty"):
            JonkerVolgenantSymmetrization.transform(self.instance, penalty=0)
        with self.assertRaisesRegex(ValueError, "penalty"):
            JonkerVolgenantSymmetrization.transform(self.instance, penalty=float("inf"))
        with self.assertRaisesRegex(ValueError, "penalty"):
            JonkerVolgenantSymmetrization.transform(self.instance, penalty=True)
        with self.assertRaisesRegex(ValueError, "TSPInstance"):
            JonkerVolgenantSymmetrization.transform([[0, 1], [1, 0]])  # type: ignore[arg-type]

    def test_rejects_inconsistent_manual_construction_and_bad_cities(self) -> None:
        symmetrized = JonkerVolgenantSymmetrization.transform(self.instance)
        with self.assertRaisesRegex(ValueError, "not the Jonker-Volgenant"):
            JonkerVolgenantSymmetrization(
                source=self.instance,
                instance=self.instance,
                penalty=symmetrized.penalty,
            )
        with self.assertRaisesRegex(ValueError, "city must"):
            symmetrized.out_node(0)
        with self.assertRaisesRegex(ValueError, "finite"):
            symmetrized.restored_objective(float("nan"))

    @staticmethod
    def _route_cost(
        route: tuple[int, ...],
        symmetrized: JonkerVolgenantSymmetrization,
        objective: str,
    ) -> float:
        matrix = getattr(symmetrized.instance, f"{objective}_matrix")
        closed = route if route[0] == route[-1] else route + (route[0],)
        return sum(matrix[start - 1][end - 1] for start, end in zip(closed, closed[1:]))

    @staticmethod
    def _original_cost(
        route: tuple[int, ...],
        instance: TSPInstance,
        objective: str,
    ) -> float:
        matrix = getattr(instance, f"{objective}_matrix")
        return sum(matrix[start - 1][end - 1] for start, end in zip(route, route[1:]))


if __name__ == "__main__":
    unittest.main()
