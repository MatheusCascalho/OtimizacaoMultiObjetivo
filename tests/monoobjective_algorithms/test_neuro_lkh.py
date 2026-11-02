import tempfile
import unittest
from itertools import permutations
from pathlib import Path

import numpy as np
import torch

from monoobjective_algorithms.interfaces import SolveRequest
from monoobjective_algorithms.tsp.heuristics import NeuroLKH, TSPSolution
from monoobjective_algorithms.tsp.heuristics.neuro_lkh_features import (
    build_graph_features,
    candidate_file_contents,
    penalty_file_contents,
    transform_atsp_guidance,
)
from monoobjective_algorithms.tsp.heuristics.neuro_lkh_model import SparseGCNModel
from monoobjective_algorithms.tsp.heuristics.neuro_lkh_training import (
    generate_synthetic_instance,
    generate_training_examples,
    held_karp_tour,
    train_model,
)
from optimization_problems.tsp import TSPInstance


class NeuroLKHTests(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = TSPInstance(
            time_matrix=[
                [0, 2, 8, 4, 5],
                [7, 0, 3, 5, 6],
                [4, 6, 0, 9, 3],
                [3, 2, 1, 0, 7],
                [4, 5, 2, 6, 0],
            ],
            distance_matrix=[
                [0, 5, 9, 3, 2],
                [8, 0, 2, 7, 4],
                [3, 7, 0, 6, 2],
                [4, 5, 8, 0, 3],
                [7, 3, 5, 4, 0],
            ],
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.checkpoint_path = Path(self.temp_dir.name) / "checkpoint.pt"
        model = SparseGCNModel(hidden_dim=8, n_gcn_layers=1, n_mlp_layers=2)
        torch.save(
            {
                "model": model.state_dict(),
                "model_config": {
                    "node_dim": 4,
                    "hidden_dim": 8,
                    "gcn_layers": 1,
                    "mlp_layers": 2,
                    "candidate_count": 4,
                    "training_node_count": 5,
                },
            },
            self.checkpoint_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_graph_features_and_lkh_files_preserve_matrix_candidates(self) -> None:
        nodes, edges, edge_index, inverse, scale = build_graph_features(
            self.instance.time_matrix, candidate_count=3
        )

        self.assertEqual(nodes.shape, (1, 5, 4))
        self.assertEqual(edges.shape, (1, 15, 1))
        self.assertEqual(edge_index.shape, (1, 5, 3))
        self.assertEqual(inverse.shape, (1, 15))
        self.assertGreater(scale, 0)
        self.assertIn("1 0 2", candidate_file_contents(((1, 2), (0,), (0,), (0,), (0,))))
        self.assertEqual(
            penalty_file_contents([0.25, -0.5], scale=100),
            "2\n1 25\n2 -50\n",
        )

    def test_atsp_guidance_matches_lkh_doubled_node_representation(self) -> None:
        candidates, penalties = transform_atsp_guidance(
            ((1, 2), (0,), (1,)),
            (0.25, -0.5, 1.0),
            candidate_limit=2,
        )

        self.assertEqual(
            candidates,
            (
                (4, 5),
                (3,),
                (4,),
                (1,),
                (0, 2),
                (0,),
            ),
        )
        self.assertEqual(penalties, (0.25, -0.5, 1.0, 0.25, -0.5, 1.0))

    def test_held_karp_matches_brute_force_for_directed_costs(self) -> None:
        costs = np.asarray(self.instance.time_matrix)
        tour = held_karp_tour(costs)
        tour_cost = sum(
            costs[source, target]
            for source, target in zip(tour, (*tour[1:], tour[0]))
        )
        best_cost = min(
            sum(
                costs[source, target]
                for source, target in zip(
                    (0, *order), (*order, 0)
                )
            )
            for order in permutations(range(1, len(costs)))
        )

        self.assertEqual(tour[0], 0)
        self.assertEqual(set(tour), set(range(len(costs))))
        self.assertEqual(tour_cost, best_cost)

    def test_synthetic_data_and_one_training_epoch(self) -> None:
        first = generate_synthetic_instance(5, np.random.default_rng(42))
        repeated = generate_synthetic_instance(5, np.random.default_rng(42))
        examples = generate_training_examples(sample_count=2, node_count=5, seed=42)
        model, losses = train_model(
            examples,
            epochs=1,
            batch_size=2,
            hidden_dim=8,
            gcn_layers=1,
            mlp_layers=2,
        )

        self.assertTrue(np.allclose(first.time_matrix, repeated.time_matrix))
        first_times = np.asarray(first.time_matrix)
        self.assertFalse(np.allclose(first_times, first_times.T))
        self.assertEqual(len(examples), 2)
        self.assertEqual(examples[0].target_edges.shape, (5,))
        self.assertEqual(len(losses), 1)
        self.assertTrue(np.isfinite(losses[0]))
        self.assertEqual(len(model.gcn_layers), 1)

    def test_solver_serializes_asymmetric_problem_and_returns_both_costs(self) -> None:
        captured: dict[str, str] = {}

        def fake_lkh(parameters: str, problem: str) -> list[int]:
            captured["parameters"] = parameters
            captured["problem"] = problem
            for line in parameters.splitlines():
                if line.startswith(("CANDIDATE_FILE =", "PI_FILE =")):
                    filepath = Path(line.split("=", 1)[1].strip())
                    self.assertTrue(filepath.is_file())
                    self.assertGreater(filepath.stat().st_size, 0)
            return [1, 2, 3, 4, 5]

        solver = NeuroLKH(
            self.checkpoint_path,
            candidate_count=4,
            candidate_limit=3,
            trials=2,
            native_solver=fake_lkh,
        )
        result = solver.solve(self.instance, SolveRequest(objective="time"))

        self.assertEqual(result.status, "feasible")
        self.assertIsInstance(result.solution, TSPSolution)
        self.assertEqual(result.solution.route, (1, 2, 3, 4, 5, 1))
        self.assertIn("TYPE : ATSP", captured["problem"])
        self.assertIn("EDGE_WEIGHT_FORMAT : FULL_MATRIX", captured["problem"])
        self.assertIn("RUNS = 2", captured["parameters"])
        self.assertEqual(
            result.objective_values["time"],
            sum(
                self.instance.time_matrix[source - 1][target - 1]
                for source, target in zip(result.solution.route, result.solution.route[1:])
            ),
        )

    def test_native_lkh_solves_symmetric_and_asymmetric_matrices(self) -> None:
        symmetric_instance = TSPInstance(
            time_matrix=self.instance.time_matrix,
            distance_matrix=[
                [0, 5, 9, 3, 2],
                [5, 0, 2, 7, 4],
                [9, 2, 0, 6, 2],
                [3, 7, 6, 0, 3],
                [2, 4, 2, 3, 0],
            ],
        )
        solver = NeuroLKH(
            self.checkpoint_path,
            candidate_count=4,
            candidate_limit=3,
            trials=1,
        )

        for instance, objective in (
            (self.instance, "time"),
            (symmetric_instance, "distance"),
        ):
            result = solver.solve(instance, SolveRequest(objective=objective))
            route = result.solution.route

            self.assertEqual(result.status, "feasible")
            self.assertEqual(route[0], route[-1])
            self.assertEqual(set(route[:-1]), set(range(1, instance.node_count + 1)))
            self.assertAlmostEqual(
                result.objective_values[objective],
                sum(
                    getattr(instance, f"{objective}_matrix")[source - 1][target - 1]
                    for source, target in zip(route, route[1:])
                ),
            )

    def test_rejects_unsupported_options_and_bad_candidate_config(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            NeuroLKH(self.checkpoint_path, candidate_count=2, candidate_limit=3)

        solver = NeuroLKH(
            self.checkpoint_path,
            candidate_count=4,
            candidate_limit=3,
            native_solver=lambda _parameters, _problem: [1, 2, 3, 4, 5],
        )
        with self.assertRaisesRegex(ValueError, "does not support objective limits"):
            solver.solve(
                self.instance,
                SolveRequest(objective="time", objective_limits={"distance": 10}),
            )
        with self.assertRaisesRegex(ValueError, "unsupported NeuroLKH parameter"):
            solver.solve(
                self.instance,
                SolveRequest(objective="time", parameters={"unknown": True}),
            )
        with self.assertRaisesRegex(FileNotFoundError, "checkpoint not found"):
            NeuroLKH(Path(self.temp_dir.name) / "missing.pt")


if __name__ == "__main__":
    unittest.main()
