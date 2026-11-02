import unittest

from multiobjective_algorithms import non_dominated_mask


class NonDominatedMaskTests(unittest.TestCase):
    def test_finds_minimization_front_and_preserves_duplicate_points(self) -> None:
        points = [
            (1, 5),
            (2, 4),
            (3, 3),
            (4, 4),
            (2, 4),
        ]

        self.assertEqual(
            non_dominated_mask(points, ("minimize", "minimize")),
            (True, True, True, False, True),
        )

    def test_respects_mixed_objective_directions(self) -> None:
        points = [(1, 1), (2, 3), (3, 2), (0, 0)]

        self.assertEqual(
            non_dominated_mask(points, ("minimize", "maximize")),
            (True, True, False, True),
        )

    def test_empty_points_returns_empty_mask(self) -> None:
        self.assertEqual(non_dominated_mask([], ("minimize", "minimize")), ())

    def test_rejects_invalid_direction_or_objective_vectors(self) -> None:
        with self.assertRaisesRegex(ValueError, "directions"):
            non_dominated_mask([(1, 2)], ("sideways", "minimize"))
        with self.assertRaisesRegex(ValueError, "match the number"):
            non_dominated_mask([(1,)], ("minimize", "minimize"))
        with self.assertRaisesRegex(ValueError, "finite real"):
            non_dominated_mask([(1, float("inf"))], ("minimize", "minimize"))
        with self.assertRaisesRegex(ValueError, "finite real"):
            non_dominated_mask([(True, 1)], ("minimize", "minimize"))


if __name__ == "__main__":
    unittest.main()
