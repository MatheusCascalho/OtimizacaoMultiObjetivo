from __future__ import annotations

from collections.abc import Callable, Sequence
from numbers import Integral
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch

from monoobjective_algorithms.interfaces import (
    SolveRequest,
    SolveResult,
    SolverCapabilities,
)
from monoobjective_algorithms.tsp.heuristics.neuro_lkh_features import (
    build_graph_features,
    candidate_file_contents,
    penalty_file_contents,
    transform_atsp_guidance,
)
from monoobjective_algorithms.tsp.heuristics.neuro_lkh_model import SparseGCNModel
from monoobjective_algorithms.tsp.heuristics.random_heuristic import TSPSolution
from optimization_problems.tsp import TSPInstance

_TSP_OBJECTIVES = frozenset({"time", "distance"})
_LKH_COST_SCALE = 10_000


def _load_native_lkh() -> Callable[[str, str], list[int]]:
    try:
        from elkai import _elkai
    except ImportError as error:
        raise RuntimeError(
            "NeuroLKH requires Elkai's native LKH extension; install the "
            "project requirements first"
        ) from error

    solve_problem = getattr(_elkai, "solve_problem", None)
    if not callable(solve_problem):
        raise RuntimeError("installed Elkai extension does not expose solve_problem")
    return solve_problem


def _checkpoint_model(
    checkpoint_path: str | Path,
) -> tuple[SparseGCNModel, int]:
    path = Path(checkpoint_path)
    if not path.is_file():
        raise FileNotFoundError(f"NeuroLKH checkpoint not found: {path}")

    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("NeuroLKH checkpoint must be a mapping")
    model_state = checkpoint.get("model")
    config = checkpoint.get("model_config")
    if not isinstance(model_state, dict) or not isinstance(config, dict):
        raise ValueError("checkpoint must contain model and model_config")
    if config.get("node_dim") != 4:
        raise ValueError("checkpoint node_dim must be 4 for matrix-derived features")

    hidden_dim = config.get("hidden_dim")
    gcn_layers = config.get("gcn_layers")
    mlp_layers = config.get("mlp_layers")
    candidate_count = config.get("candidate_count")
    for name, value in (
        ("hidden_dim", hidden_dim),
        ("gcn_layers", gcn_layers),
        ("mlp_layers", mlp_layers),
        ("candidate_count", candidate_count),
    ):
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
            raise ValueError(f"checkpoint {name} must be a positive integer")

    model = SparseGCNModel(
        hidden_dim=int(hidden_dim),
        n_gcn_layers=int(gcn_layers),
        n_mlp_layers=int(mlp_layers),
    )
    model.load_state_dict(model_state, strict=True)
    model.eval()
    return model, int(candidate_count)


def _problem_text(costs: np.ndarray) -> str:
    n_nodes = len(costs)
    problem_type = "TSP" if np.array_equal(costs, costs.T) else "ATSP"
    lines = [
        "NAME : neuro_lkh",
        f"TYPE : {problem_type}",
        f"DIMENSION : {n_nodes}",
        "EDGE_WEIGHT_TYPE : EXPLICIT",
        "EDGE_WEIGHT_FORMAT : FULL_MATRIX",
        "EDGE_WEIGHT_SECTION",
    ]
    lines.extend(" ".join(format(float(value), ".15g") for value in row) for row in costs)
    lines.append("EOF")
    return "\n".join(lines) + "\n"


class NeuroLKH:
    """Trainable SGN guidance with the LKH C backend for explicit TSP costs."""

    algorithm_id = "neuro-lkh"
    capabilities = SolverCapabilities(supports_objective_limits=False)

    def __init__(
        self,
        model_path: str | Path,
        candidate_count: int = 20,
        candidate_limit: int = 5,
        trials: int = 10,
        seed: int | None = 1234,
        native_solver: Callable[[str, str], list[int]] | None = None,
    ) -> None:
        self._validate_positive_integer(candidate_count, "candidate_count")
        self._validate_positive_integer(candidate_limit, "candidate_limit")
        self._validate_positive_integer(trials, "trials")
        self._validate_seed(seed)
        if candidate_limit > candidate_count:
            raise ValueError("candidate_limit cannot exceed candidate_count")

        self._model, self._trained_candidate_count = _checkpoint_model(model_path)
        self._candidate_count = candidate_count
        self._candidate_limit = candidate_limit
        self._trials = trials
        self._seed = seed
        self._native_solver = native_solver

    def solve(
        self,
        instance: TSPInstance,
        request: SolveRequest,
    ) -> SolveResult[TSPSolution]:
        if request.objective not in _TSP_OBJECTIVES:
            raise ValueError("objective must be 'time' or 'distance'")
        if request.objective_limits:
            raise ValueError("NeuroLKH does not support objective limits")
        unknown_parameters = set(request.parameters) - {"seed", "trials"}
        if unknown_parameters:
            names = ", ".join(sorted(unknown_parameters))
            raise ValueError(f"unsupported NeuroLKH parameter(s): {names}")

        seed = request.parameters.get("seed", self._seed)
        self._validate_seed(seed)
        trials = request.parameters.get("trials", self._trials)
        self._validate_positive_integer(trials, "trials")

        costs = np.asarray(
            instance.time_matrix
            if request.objective == "time"
            else instance.distance_matrix,
            dtype=np.float64,
        )
        if np.any(costs < 0):
            raise ValueError("NeuroLKH requires non-negative costs for LKH")

        node_features, edge_features, edge_index, inverse_index, cost_scale = (
            build_graph_features(costs, self._candidate_count)
        )
        n_edges = edge_index.shape[2]
        with torch.inference_mode():
            edge_probabilities, node_penalties = self._model(
                torch.from_numpy(node_features).float(),
                torch.from_numpy(edge_features).float(),
                torch.from_numpy(edge_index).long().reshape(1, -1),
                torch.from_numpy(inverse_index).long(),
                n_edges,
            )
        candidate_count = min(self._candidate_limit, n_edges)
        candidates = self._rank_candidates(
            edge_index[0],
            edge_probabilities[0].cpu().numpy(),
            candidate_count,
        )
        penalties = (
            node_penalties[0, :, 0].cpu().numpy().astype(np.float64) * cost_scale
        )
        if not np.array_equal(costs, costs.T):
            candidates, penalties = transform_atsp_guidance(
                candidates,
                penalties,
                candidate_count,
            )
        route = self._run_lkh(costs, candidates, penalties, int(seed or 1), int(trials))
        if len(route) != instance.node_count or set(route) != set(range(1, instance.node_count + 1)):
            raise RuntimeError("LKH returned an invalid Hamiltonian tour")
        closed_route = (*route, route[0])

        return SolveResult(
            status="feasible",
            solution=TSPSolution(route=closed_route),
            objective_values={
                "time": self._tour_cost(
                    np.asarray(instance.time_matrix, dtype=np.float64), route
                ),
                "distance": self._tour_cost(
                    np.asarray(instance.distance_matrix, dtype=np.float64), route
                ),
            },
        )

    @staticmethod
    def _rank_candidates(
        edge_index: np.ndarray,
        probabilities: np.ndarray,
        candidate_limit: int,
    ) -> tuple[tuple[int, ...], ...]:
        candidates = []
        for source, neighbors in enumerate(edge_index):
            ranked = sorted(
                range(len(neighbors)),
                key=lambda index: (
                    -float(probabilities[source, index]),
                    int(neighbors[index]),
                ),
            )
            candidates.append(
                tuple(int(neighbors[index]) for index in ranked[:candidate_limit])
            )
        return tuple(candidates)

    def _run_lkh(
        self,
        costs: np.ndarray,
        candidates: Sequence[Sequence[int]],
        penalties: Sequence[float],
        seed: int,
        trials: int,
    ) -> tuple[int, ...]:
        native_solver = self._native_solver or _load_native_lkh()
        with TemporaryDirectory(prefix="neurolkh-") as directory:
            candidate_path = Path(directory) / "candidates.txt"
            penalty_path = Path(directory) / "penalties.txt"
            candidate_path.write_text(
                candidate_file_contents(candidates), encoding="ascii"
            )
            penalty_path.write_text(
                penalty_file_contents(penalties, _LKH_COST_SCALE),
                encoding="ascii",
            )
            parameters = "\n".join(
                (
                    "PROBLEM_FILE = :stdin:",
                    f"RUNS = {trials}",
                    f"SEED = {seed}",
                    f"SCALE = {_LKH_COST_SCALE}",
                    f"MAX_CANDIDATES = {len(candidates[0])}",
                    "MOVE_TYPE = 5",
                    "PATCHING_C = 3",
                    "PATCHING_A = 2",
                    "SUBGRADIENT = NO",
                    "TRACE_LEVEL = 0",
                    f"CANDIDATE_FILE = {candidate_path}",
                    f"PI_FILE = {penalty_path}",
                    "",
                )
            )
            result = native_solver(parameters, _problem_text(costs))

        if not isinstance(result, list) or any(
            isinstance(node, bool) or not isinstance(node, Integral) for node in result
        ):
            raise RuntimeError("LKH backend returned an invalid tour representation")
        return tuple(int(node) for node in result)

    @staticmethod
    def _tour_cost(costs: np.ndarray, route: Sequence[int]) -> float:
        zero_based = tuple(node - 1 for node in route)
        return sum(
            float(costs[source, target])
            for source, target in zip(zero_based, (*zero_based[1:], zero_based[0]))
        )

    @staticmethod
    def _validate_seed(seed: object) -> None:
        if seed is not None and (
            isinstance(seed, bool) or not isinstance(seed, Integral)
        ):
            raise ValueError("seed must be an integer or None")

    @staticmethod
    def _validate_positive_integer(value: object, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
