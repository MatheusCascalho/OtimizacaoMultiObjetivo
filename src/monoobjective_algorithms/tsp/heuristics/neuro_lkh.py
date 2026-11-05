from __future__ import annotations

import json
import subprocess
import tempfile
from math import isfinite
from numbers import Integral
from pathlib import Path

from monoobjective_algorithms.interfaces import (
    SolveRequest,
    SolveResult,
    SolverCapabilities,
)
from monoobjective_algorithms.tsp.heuristics.random_heuristic import TSPSolution
from optimization_problems.tsp import (
    JonkerVolgenantSymmetrization,
    TSPInstance,
    WeightedCostScalarization,
)

_TSP_OBJECTIVES = frozenset({"time", "distance"})
_PARAMETERS = frozenset({"weight", "seed", "lkh_trials"})


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_model_path() -> Path:
    return _repo_root() / "third_party" / "NeuroLKH" / "pretrained" / "neurolkh.pt"


def _validate_weight(weight: object) -> float:
    if isinstance(weight, bool):
        raise ValueError("weight must be a finite number in the interval [0, 1]")
    try:
        number = float(weight)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("weight must be a finite number in the interval [0, 1]") from error
    if not isfinite(number) or not 0 <= number <= 1:
        raise ValueError("weight must be a finite number in the interval [0, 1]")
    return number


def _validate_lkh_trials(trials: object) -> int:
    if isinstance(trials, bool) or not isinstance(trials, Integral) or int(trials) <= 0:
        raise ValueError("lkh_trials must be a positive integer")
    return int(trials)


def _route_cost(matrix: tuple[tuple[float, ...], ...], route: tuple[int, ...]) -> float:
    return sum(
        matrix[source - 1][target - 1]
        for source, target in zip(route, route[1:])
    )


def _failed() -> SolveResult[TSPSolution]:
    return SolveResult(status="failed", solution=None, objective_values={})


class SubprocessNeuroLKHBackend:
    """Run the pretrained network and the SWIG LKH solver in Python 3.11."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path

    def solve_symmetric(
        self,
        cost_matrix: tuple[tuple[float, ...], ...],
        *,
        trials: int,
        seed: int | None,
    ) -> tuple[int, ...]:
        root = _repo_root() / "third_party" / "NeuroLKH"
        if not root.is_dir():
            raise RuntimeError(f"NeuroLKH checkout not found: {root}")
        interpreter = root / ".venv" / "bin" / "python"
        if not interpreter.is_file():
            interpreter = Path("python3.11")
        script = Path(__file__).with_name("neurolkh_worker.py")
        payload = {
            "cost_matrix": [list(row) for row in cost_matrix],
            "trials": trials,
            "seed": seed,
            "model_path": str(self.model_path),
        }
        with tempfile.NamedTemporaryFile(prefix="neurolkh-", suffix=".json", delete=False) as handle:
            output_path = Path(handle.name)
        try:
            completed = subprocess.run(
                [str(interpreter), str(script), str(output_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(root),
                check=False,
            )
            if not output_path.is_file() or output_path.stat().st_size == 0:
                detail = completed.stderr.strip() or completed.stdout.strip() or "no solver output"
                raise RuntimeError(f"NeuroLKH process failed: {detail}")
            body = json.loads(output_path.read_text(encoding="utf-8"))
            if completed.returncode != 0 or not body.get("ok"):
                detail = body.get("error") or completed.stderr.strip() or "NeuroLKH failed"
                raise RuntimeError(str(detail))
            return tuple(int(node) for node in body["tour"])
        finally:
            output_path.unlink(missing_ok=True)


class NeuroLKH:
    """Solve one scalarized TSP with the pretrained NeuroLKH model and LKH."""

    algorithm_id = "neuro-lkh"
    capabilities = SolverCapabilities(supports_objective_limits=False)

    def __init__(
        self,
        seed: int | None = None,
        weight: float = 0.5,
        lkh_trials: int = 1000,
        model_path: str | Path | None = None,
        backend: object | None = None,
    ) -> None:
        self._validate_seed(seed)
        self._seed = seed
        self._weight = _validate_weight(weight)
        self._lkh_trials = _validate_lkh_trials(lkh_trials)
        self._model_path = Path(model_path) if model_path is not None else _default_model_path()
        self._backend = backend

    def solve(
        self,
        instance: TSPInstance,
        request: SolveRequest,
    ) -> SolveResult[TSPSolution]:
        if request.objective not in _TSP_OBJECTIVES:
            raise ValueError("objective must be 'time' or 'distance'")
        if request.objective_limits:
            raise ValueError("NeuroLKH does not support objective limits")

        unknown_parameters = set(request.parameters) - _PARAMETERS
        if unknown_parameters:
            names = ", ".join(sorted(unknown_parameters))
            raise ValueError(f"unsupported NeuroLKH parameter(s): {names}")

        weight = (
            _validate_weight(request.parameters["weight"])
            if "weight" in request.parameters
            else self._weight
        )
        if "seed" in request.parameters:
            seed = request.parameters["seed"]
            self._validate_seed(seed)
        else:
            seed = self._seed
        if seed is not None:
            seed = int(seed)
        trials = (
            _validate_lkh_trials(request.parameters["lkh_trials"])
            if "lkh_trials" in request.parameters
            else self._lkh_trials
        )

        scalarized = WeightedCostScalarization.scalarize(instance, weight)
        unified = TSPInstance(
            time_matrix=scalarized.cost_matrix,
            distance_matrix=scalarized.cost_matrix,
        )
        symmetrized = JonkerVolgenantSymmetrization.transform(unified)
        try:
            symmetric_route = self._resolve_backend().solve_symmetric(
                symmetrized.instance.time_matrix,
                trials=trials,
                seed=seed,
            )
            route = symmetrized.original_route(symmetric_route)
        except Exception:
            return _failed()

        total_time = _route_cost(instance.time_matrix, route)
        total_distance = _route_cost(instance.distance_matrix, route)
        if not isfinite(total_time) or not isfinite(total_distance):
            return _failed()
        return SolveResult(
            status="feasible",
            solution=TSPSolution(route=route),
            objective_values={"time": total_time, "distance": total_distance},
        )

    def _resolve_backend(self) -> SubprocessNeuroLKHBackend:
        if self._backend is None:
            self._backend = SubprocessNeuroLKHBackend(self._model_path)
        return self._backend

    @staticmethod
    def _validate_seed(seed: object) -> None:
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, Integral)):
            raise ValueError("seed must be an integer or None")
