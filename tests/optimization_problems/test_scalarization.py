import unittest

from optimization_problems.tsp import (
    TSPInstance,
    WeightedCostScalarization,
    normalize_matrix,
    unify_costs,
)


class WeightedCostScalarizationTests(unittest.TestCase):
    def test_normalizes_each_matrix_onto_the_unit_interval(self) -> None:
        normalized = normalize_matrix(
            [
                [2, 4],
                [6, 8],
            ]
        )

        self.assertEqual(normalized, ((0.0, 1 / 3), (2 / 3, 1.0)))
        self.assertEqual(normalize_matrix([[5, -1], [3, 7]]), ((0.75, 0.0), (0.5, 1.0)))
        self.assertEqual(normalize_matrix([[4, 4], [4, 4]]), ((0.0, 0.0), (0.0, 0.0)))

    def test_unifies_normalized_matrices_with_the_given_weight(self) -> None:
        normalized_time = ((0.0, 1 / 3), (2 / 3, 1.0))
        normalized_distance = ((0.0, 0.0), (0.0, 1.0))

        self.assertEqual(
            unify_costs(normalized_time, normalized_distance, 0.25),
            ((0.0, 1 / 12), (1 / 6, 1.0)),
        )
        self.assertEqual(unify_costs(normalized_time, normalized_distance, 1), normalized_time)
        self.assertEqual(
            unify_costs(normalized_time, normalized_distance, 0),
            normalized_distance,
        )

    def test_scalarize_normalizes_the_instance_and_builds_the_weighted_cost(self) -> None:
        instance = TSPInstance(
            time_matrix=[[2, 4], [6, 8]],
            distance_matrix=[[1, 1], [1, 5]],
        )

        scalarized = WeightedCostScalarization.scalarize(instance, weight=0.25)

        self.assertEqual(scalarized.weight, 0.25)
        self.assertEqual(scalarized.normalized_time, ((0.0, 1 / 3), (2 / 3, 1.0)))
        self.assertEqual(scalarized.normalized_distance, ((0.0, 0.0), (0.0, 1.0)))
        self.assertEqual(scalarized.cost_matrix, ((0.0, 1 / 12), (1 / 6, 1.0)))
        for row in scalarized.cost_matrix:
            for value in row:
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 1)

    def test_rejects_invalid_matrices_weights_and_ranges(self) -> None:
        with self.assertRaisesRegex(ValueError, "square"):
            normalize_matrix([[0, 1]])
        with self.assertRaisesRegex(ValueError, "finite"):
            normalize_matrix([[0, float("nan")], [1, 0]])
        with self.assertRaisesRegex(ValueError, "same dimensions"):
            unify_costs([[0, 1], [1, 0]], [[0, 1, 0], [1, 0, 1], [0, 1, 0]], 0.5)
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            unify_costs([[0, 2], [1, 0]], [[0, 1], [1, 0]], 0.5)
        with self.assertRaisesRegex(ValueError, "weight"):
            unify_costs([[0, 1], [1, 0]], [[0, 1], [1, 0]], 1.1)
        with self.assertRaisesRegex(ValueError, "weight"):
            unify_costs([[0, 1], [1, 0]], [[0, 1], [1, 0]], True)
        with self.assertRaisesRegex(ValueError, "TSPInstance"):
            WeightedCostScalarization.scalarize([[0, 1], [1, 0]], 0.5)  # type: ignore[arg-type]

    def test_rejects_a_matrix_that_does_not_match_the_instance(self) -> None:
        instance = TSPInstance(
            time_matrix=[[0, 2], [3, 0]],
            distance_matrix=[[0, 4], [5, 0]],
        )
        scalarized = WeightedCostScalarization.scalarize(instance, 0.5)

        with self.assertRaisesRegex(ValueError, "weighted scalarization"):
            WeightedCostScalarization(
                source=instance,
                weight=scalarized.weight,
                normalized_time=scalarized.normalized_time,
                normalized_distance=scalarized.normalized_distance,
                cost_matrix=((0.0, 0.0), (0.0, 0.0)),
            )


if __name__ == "__main__":
    unittest.main()
