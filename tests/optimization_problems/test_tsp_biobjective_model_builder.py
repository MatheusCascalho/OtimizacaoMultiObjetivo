import unittest

from pyomo.environ import Binary, minimize, value

from optimization_problems.tsp import TSPInstance
from optimization_problems.tsp.models import TSPBiobjectiveModelBuilder


class TSPBiobjectiveModelBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = TSPInstance(
            time_matrix=[
                [0, 2, 8],
                [7, 0, 3],
                [4, 6, 0],
            ],
            distance_matrix=[
                [0, 5, 9],
                [8, 0, 2],
                [3, 7, 0],
            ],
        )
        self.builder = TSPBiobjectiveModelBuilder()

    def test_builds_directed_degree_and_mtz_constraints(self) -> None:
        model = self.builder.build(self.instance)

        self.assertEqual(len(model.x), 3 * 2)
        self.assertTrue(all(variable.domain is Binary for variable in model.x.values()))
        self.assertEqual(len(model.u), 2)
        self.assertEqual(len(model.out_degree), 3)
        self.assertEqual(len(model.in_degree), 3)
        self.assertEqual(len(model.mtz), 2)
        self.assertEqual(model.u[2].bounds, (1, 2))
        self.assertIs(model.objective.expr, model.total_time)
        self.assertEqual(model.objective.sense, minimize)

    def test_keeps_both_costs_and_applies_secondary_objective_limit(self) -> None:
        model = self.builder.build(
            self.instance,
            objective="time",
            objective_limits={"distance": 10},
        )
        self._set_three_node_cycle(model)

        self.assertEqual(value(model.total_time), 9)
        self.assertEqual(value(model.total_distance), 10)
        self.assertEqual(value(model.distance_limit.body), 10)
        self.assertEqual(value(model.distance_limit.upper), 10)
        for constraint in model.out_degree.values():
            self.assertEqual(value(constraint.body), 1)
        for constraint in model.in_degree.values():
            self.assertEqual(value(constraint.body), 1)
        for constraint in model.mtz.values():
            self.assertLessEqual(value(constraint.body), value(constraint.upper))

    def test_can_minimize_distance_with_time_limit(self) -> None:
        model = self.builder.build(
            self.instance,
            objective="distance",
            objective_limits={"time": 12},
        )

        self.assertIs(model.objective.expr, model.total_distance)
        self.assertTrue(hasattr(model, "time_limit"))

    def test_rejects_constraints_on_primary_or_unknown_objectives(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-primary"):
            self.builder.build(
                self.instance,
                objective="time",
                objective_limits={"time": 12},
            )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.builder.build(
                self.instance,
                objective_limits={"cost": 12},
            )
        with self.assertRaisesRegex(ValueError, "objective must"):
            self.builder.build(self.instance, objective="cost")

    def test_rejects_non_finite_objective_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            self.builder.build(
                self.instance,
                objective_limits={"distance": float("inf")},
            )
        with self.assertRaisesRegex(ValueError, "finite"):
            self.builder.build(
                self.instance,
                objective_limits={"distance": True},
            )

    def test_instance_requires_aligned_finite_square_matrices(self) -> None:
        with self.assertRaisesRegex(ValueError, "same dimensions"):
            TSPInstance([[0, 1], [1, 0]], [[0, 1, 2], [1, 0, 3], [2, 3, 0]])
        with self.assertRaisesRegex(ValueError, "square"):
            TSPInstance([[0, 1]], [[0, 1]])
        with self.assertRaisesRegex(ValueError, "finite"):
            TSPInstance([[0, float("nan")], [1, 0]], [[0, 1], [1, 0]])
        with self.assertRaisesRegex(ValueError, "finite"):
            TSPInstance([[0, "1"], [1, 0]], [[0, 1], [1, 0]])

    @staticmethod
    def _set_three_node_cycle(model) -> None:
        for arc in model.arcs:
            model.x[arc].value = 0
        for arc in ((1, 2), (2, 3), (3, 1)):
            model.x[arc].value = 1
        model.u[2].value = 1
        model.u[3].value = 2


if __name__ == "__main__":
    unittest.main()
