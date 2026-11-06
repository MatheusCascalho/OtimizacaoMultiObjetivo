import math

import pytest

from monoobjective_algorithms.interfaces import SolveRequest, SolveResult, SolverCapabilities
from multiobjective_algorithms import (
    ObjectiveSpec,
    ReferencePointError,
    compute_reference_points,
    estimate_reference_points,
    euclidean_distance,
    normalize_objectives,
    normalized_euclidean_distance,
)

MIN_F1_F2 = (
    ObjectiveSpec("f1", "minimize"),
    ObjectiveSpec("f2", "minimize"),
)


class QuadraticSolver:
    """Analytic solver for min x², min (x-2)², x in [0, 2]."""

    algorithm_id = "quadratic-analytic"
    capabilities = SolverCapabilities(supports_objective_limits=True)

    def solve(self, instance: object, request: SolveRequest) -> SolveResult[float]:
        lower = 0.0
        upper = 2.0
        for name, bound in request.objective_limits.items():
            if bound < 0:
                return SolveResult(status="infeasible", solution=None, objective_values={})
            if name == "f1":
                upper = min(upper, math.sqrt(bound))
            elif name == "f2":
                lower = max(lower, 2.0 - math.sqrt(bound))
        if lower > upper + 1e-12:
            return SolveResult(status="infeasible", solution=None, objective_values={})
        if request.objective == "f1":
            decision = min(max(0.0, lower), upper)
        elif request.objective == "f2":
            decision = min(max(2.0, lower), upper)
        else:
            return SolveResult(status="failed", solution=None, objective_values={})
        return SolveResult(
            status="optimal",
            solution=decision,
            objective_values={"f1": decision * decision, "f2": (decision - 2.0) ** 2},
        )


class DiscreteSolver:
    algorithm_id = "discrete"
    capabilities = SolverCapabilities(supports_objective_limits=True)

    def solve(self, instance: list[dict[str, float]], request: SolveRequest) -> SolveResult[dict[str, float]]:
        feasible = [
            point
            for point in instance
            if all(point[name] <= bound for name, bound in request.objective_limits.items())
        ]
        if not feasible:
            return SolveResult(status="infeasible", solution=None, objective_values={})
        best = min(feasible, key=lambda point: point[request.objective])
        return SolveResult(status="optimal", solution=best, objective_values=dict(best))


class StatusSolver:
    def __init__(self, status: str, *, constrained_status: str | None = None) -> None:
        self.algorithm_id = "status"
        self.capabilities = SolverCapabilities(supports_objective_limits=True)
        self.status = status
        self.constrained_status = constrained_status

    def solve(self, instance: object, request: SolveRequest) -> SolveResult[None]:
        status = self.constrained_status if request.objective_limits and self.constrained_status else self.status
        if status != "optimal":
            return SolveResult(status=status, solution=None, objective_values={})
        return SolveResult(status="optimal", solution=None, objective_values={"f1": 1.0, "f2": 2.0})


class NoLimitSolver:
    algorithm_id = "plain"
    capabilities = SolverCapabilities(supports_objective_limits=False)

    def solve(self, instance: object, request: SolveRequest) -> SolveResult[None]:
        raise AssertionError("o solver não deveria ser chamado")


class InconsistentSolver:
    algorithm_id = "inconsistent"
    capabilities = SolverCapabilities(supports_objective_limits=True)

    def solve(self, instance: object, request: SolveRequest) -> SolveResult[None]:
        if request.objective == "f1" and not request.objective_limits:
            values = {"f1": 5.0, "f2": 0.0}
        elif request.objective == "f2" and request.objective_limits:
            values = {"f1": 5.0, "f2": 1.0}
        elif request.objective == "f2":
            values = {"f1": 0.0, "f2": 3.0}
        else:
            values = {"f1": 0.0, "f2": 3.0}
        return SolveResult(status="optimal", solution=None, objective_values=values)


def test_section_8_quadratic_example_is_exact_with_zero_tolerance() -> None:
    result = compute_reference_points(QuadraticSolver(), "quadratic", MIN_F1_F2, delta=0)

    assert result.method == "lexicographic"
    assert result.utopian_values() == {"f1": 0.0, "f2": 0.0}
    assert result.nadir_values() == {"f1": 4.0, "f2": 4.0}
    assert result.extreme_best_first == 0.0
    assert result.extreme_best_second == 2.0
    assert result.warnings == ()
    assert normalize_objectives((1.0, 1.0), result) == (0.25, 0.25)


def test_positive_delta_stays_next_to_the_quadratic_nadir() -> None:
    result = compute_reference_points(QuadraticSolver(), "quadratic", MIN_F1_F2, delta=1e-6)

    assert result.utopian_values() == {"f1": 0.0, "f2": 0.0}
    assert result.nadir[0] == pytest.approx(3.996001)
    assert result.nadir[1] == pytest.approx(3.996001)


def test_lexicographic_nadir_is_not_the_naive_payoff_of_an_alternative_optimum() -> None:
    points = [
        {"f1": 0.0, "f2": 5.0},
        {"f1": 0.0, "f2": 1.0},
        {"f1": 3.0, "f2": 0.0},
    ]

    result = compute_reference_points(DiscreteSolver(), points, MIN_F1_F2, delta=0)

    assert points[0]["f2"] == 5.0
    assert result.utopian_values() == {"f1": 0.0, "f2": 0.0}
    assert result.nadir_values() == {"f1": 3.0, "f2": 1.0}


def test_sample_estimate_matches_lexicographic_selection_and_is_deterministic() -> None:
    samples = (
        {"f1": 0.0, "f2": 5.0},
        {"f1": 0.0, "f2": 1.0},
        {"f1": 3.0, "f2": 0.0},
        {"f1": 4.0, "f2": 4.0},
    )

    first = estimate_reference_points(samples, MIN_F1_F2)
    second = estimate_reference_points(samples, MIN_F1_F2)

    assert first == second
    assert first.method == "approximate_front"
    assert first.utopian_values() == {"f1": 0.0, "f2": 0.0}
    assert first.nadir_values() == {"f1": 3.0, "f2": 1.0}


def test_quadratic_extremes_estimated_from_the_sample_match_section_8() -> None:
    result = estimate_reference_points(
        ({"f1": 0.0, "f2": 4.0}, {"f1": 4.0, "f2": 0.0}),
        MIN_F1_F2,
    )

    assert result.utopian == (0.0, 0.0)
    assert result.nadir == (4.0, 4.0)


def test_non_conflicting_objectives_warn_and_normalization_stays_finite() -> None:
    result = estimate_reference_points(({"f1": 2.0, "f2": 3.0},), MIN_F1_F2)

    assert result.utopian == result.nadir == (2.0, 3.0)
    assert result.warnings[0].code == "non_conflicting_objectives"
    assert normalize_objectives((2.0, 3.0), result) == (0.0, 0.0)
    assert all(math.isfinite(component) for component in normalize_objectives((2.0, 3.0), result))


def test_maximization_is_reported_in_the_original_sense() -> None:
    objectives = (
        ObjectiveSpec("quality", "maximize"),
        ObjectiveSpec("cost", "minimize"),
    )
    estimated = estimate_reference_points(
        ({"quality": 5.0, "cost": 1.0}, {"quality": 1.0, "cost": 0.0}),
        objectives,
    )
    solved = compute_reference_points(
        DiscreteSolver(),
        [{"quality": -5.0, "cost": 1.0}, {"quality": -1.0, "cost": 0.0}],
        objectives,
        delta=0,
    )

    assert estimated.utopian_values() == {"quality": 5.0, "cost": 0.0}
    assert estimated.nadir_values() == {"quality": 1.0, "cost": 1.0}
    assert solved.utopian_values() == estimated.utopian_values()
    assert solved.nadir_values() == estimated.nadir_values()
    assert normalize_objectives((5.0, 0.0), estimated) == (0.0, 0.0)
    assert normalize_objectives((1.0, 1.0), estimated) == (1.0, 1.0)


def test_infeasible_unbounded_and_inconsistent_stages_are_explicit() -> None:
    with pytest.raises(ReferencePointError, match="problema inviável") as infeasible:
        compute_reference_points(StatusSolver("infeasible"), None, MIN_F1_F2)
    assert infeasible.value.stage == "L1"

    with pytest.raises(ReferencePointError, match="ilimitado") as unbounded:
        compute_reference_points(StatusSolver("failed"), None, MIN_F1_F2)
    assert unbounded.value.stage == "L1"

    with pytest.raises(ReferencePointError, match="problema inviável") as constrained:
        compute_reference_points(
            StatusSolver("optimal", constrained_status="infeasible"),
            None,
            MIN_F1_F2,
        )
    assert constrained.value.stage == "L2"

    with pytest.raises(ReferencePointError, match="Inconsistência numérica"):
        compute_reference_points(InconsistentSolver(), None, MIN_F1_F2, delta=0)


def test_solver_without_objective_limits_is_rejected_before_solve() -> None:
    with pytest.raises(ValueError, match="limites"):
        compute_reference_points(NoLimitSolver(), None, MIN_F1_F2)


def test_estimate_rejects_empty_non_finite_and_wrong_dimension() -> None:
    with pytest.raises(ReferencePointError, match="Não há soluções"):
        estimate_reference_points((), MIN_F1_F2)
    with pytest.raises(ValueError, match="exatamente 2"):
        estimate_reference_points(({"f1": 1.0},), (ObjectiveSpec("f1", "minimize"),))
    with pytest.raises(ValueError, match="finitos"):
        estimate_reference_points(({"f1": 1.0, "f2": math.inf},), MIN_F1_F2)


def test_normalized_euclidean_distance_uses_the_utopian_nadir_scale() -> None:
    reference = estimate_reference_points(
        (
            {"f1": 0.0, "f2": 8.0},
            {"f1": 6.0, "f2": 0.0},
        ),
        MIN_F1_F2,
    )
    assert reference.utopian == (0.0, 0.0)
    assert reference.nadir == (6.0, 8.0)
    assert euclidean_distance((0.0, 0.0), (3.0, 4.0)) == 5.0
    assert normalized_euclidean_distance((3.0, 4.0), reference.utopian, reference) == pytest.approx(
        math.hypot(0.5, 0.5)
    )
    assert normalized_euclidean_distance((3.0, 4.0), reference.nadir, reference) == pytest.approx(
        math.hypot(0.5, 0.5)
    )


def test_normalized_euclidean_distance_is_zero_on_a_null_range() -> None:
    reference = estimate_reference_points(({"f1": 2.0, "f2": 3.0},), MIN_F1_F2)
    assert normalized_euclidean_distance((9.0, 9.0), reference.utopian, reference) == 0.0


def test_normalized_euclidean_distance_respects_maximization() -> None:
    reference = estimate_reference_points(
        (
            {"quality": 10.0, "cost": 4.0},
            {"quality": 4.0, "cost": 0.0},
        ),
        (
            ObjectiveSpec("quality", "maximize"),
            ObjectiveSpec("cost", "minimize"),
        ),
    )
    assert normalized_euclidean_distance((7.0, 2.0), reference.utopian, reference) == pytest.approx(
        math.hypot(0.5, 0.5)
    )
