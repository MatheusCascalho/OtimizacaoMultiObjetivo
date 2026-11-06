"""Utopian point and nadir (anti-utopian) for exactly two objectives.

The definitions follow ``docs/algorithms/solucao_utopica_e_antiutopica.md``.
Both entries below work in minimization space and convert the reported
points back to the original objective directions.

``compute_reference_points`` is the lexicographic procedure (sections 4.2
and 5). The injected solver must minimize each objective and treat
``objective_limits`` as upper bounds in that minimization space. A
``maximize`` objective is stored negated inside the solver; this function
restores the original sign.

``estimate_reference_points`` applies the same lexicographic selection to a
finite sample (section 6.1). On a sampled frontier this is an estimate: the
nadir is the nadir of the non-dominated sample, not the nadir of the whole
feasible set, and it is not the component-wise worst point of that set.
Lexicographic selection avoids the naive payoff table (section 4.3), which
overestimates the nadir when an individual optimum is not unique.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import dist, isfinite
from numbers import Real
from typing import Mapping, Sequence

from multiobjective_algorithms.dominance import ObjectiveDirection
from monoobjective_algorithms.interfaces import MonoobjectiveSolver, SolveRequest

logger = logging.getLogger(__name__)

_NON_CONFLICTING_CODE = "non_conflicting_objectives"
_NON_CONFLICTING_MESSAGE = (
    "Objetivos não conflitantes: a faixa de variação de pelo menos um objetivo é nula."
)


class ReferencePointError(ValueError):
    """The utopian/nadir calculation cannot be completed."""

    def __init__(self, message: str, *, stage: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class ObjectiveSpec:
    id: str
    direction: ObjectiveDirection

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("cada objetivo precisa de um identificador")
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("a direção do objetivo deve ser 'minimize' ou 'maximize'")


@dataclass(frozen=True)
class ReferenceWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ReferencePoints:
    objectives: tuple[ObjectiveSpec, ...]
    utopian: tuple[float, ...]
    nadir: tuple[float, ...]
    warnings: tuple[ReferenceWarning, ...]
    method: str
    extreme_best_first: object | None = None
    extreme_best_second: object | None = None

    def utopian_values(self) -> dict[str, float]:
        return _as_mapping(self.objectives, self.utopian)

    def nadir_values(self) -> dict[str, float]:
        return _as_mapping(self.objectives, self.nadir)


def compute_reference_points(
    solver: MonoobjectiveSolver,
    instance: object,
    objectives: Sequence[ObjectiveSpec],
    *,
    delta: float = 1e-6,
    epsilon: float = 1e-8,
    parameters: Mapping[str, object] | None = None,
) -> ReferencePoints:
    """Lexicographic utopian point and nadir (sections 4.2 and 5).

    ``delta`` is the relative tolerance of section 4.4a:
    ``δ * max(1, |z|)``. Pass ``delta=0`` to keep the optimal value as an
    exact upper bound, which is what the numeric example in section 8 uses.
    """

    specs = _two_objectives(objectives)
    numeric_delta = _non_negative_finite(delta, "delta")
    numeric_epsilon = _non_negative_finite(epsilon, "epsilon")
    if not solver.capabilities.supports_objective_limits:
        raise ValueError("o solver não aceita limites em objetivos secundários")

    solve_parameters = dict(parameters or {})
    first, second = specs
    z1_u, _solution_l1 = _solve_objective(
        solver, instance, first.id, {}, "L1", solve_parameters
    )
    z2_n, extreme_first = _solve_objective(
        solver,
        instance,
        second.id,
        {first.id: z1_u + _absolute_tolerance(z1_u, numeric_delta)},
        "L2",
        solve_parameters,
    )
    z2_u, _solution_l3 = _solve_objective(
        solver, instance, second.id, {}, "L3", solve_parameters
    )
    z1_n, extreme_second = _solve_objective(
        solver,
        instance,
        first.id,
        {second.id: z2_u + _absolute_tolerance(z2_u, numeric_delta)},
        "L4",
        solve_parameters,
    )
    return _assemble(
        specs,
        utopian_min=(z1_u, z2_u),
        nadir_min=(z1_n, z2_n),
        epsilon=numeric_epsilon,
        tolerance=max(
            _absolute_tolerance(z1_u, numeric_delta),
            _absolute_tolerance(z2_u, numeric_delta),
        ),
        method="lexicographic",
        extreme_best_first=extreme_first,
        extreme_best_second=extreme_second,
    )


def estimate_reference_points(
    samples: Sequence[Mapping[str, float]],
    objectives: Sequence[ObjectiveSpec],
    *,
    epsilon: float = 1e-8,
) -> ReferencePoints:
    """Lexicographic utopian point and nadir of a finite sample (section 6.1)."""

    specs = _two_objectives(objectives)
    numeric_epsilon = _non_negative_finite(epsilon, "epsilon")
    if not samples:
        raise ReferencePointError(
            "Não há soluções mapeadas para estimar os pontos de referência."
        )

    minimized: list[tuple[float, float]] = []
    for sample in samples:
        original = tuple(_read_sample_value(sample, spec.id) for spec in specs)
        minimized.append(
            tuple(
                _negate_if_maximize(value, spec.direction)
                for value, spec in zip(original, specs)
            )
        )

    z1_u = min(point[0] for point in minimized)
    z2_n = min(point[1] for point in minimized if point[0] <= z1_u + numeric_epsilon)
    z2_u = min(point[1] for point in minimized)
    z1_n = min(point[0] for point in minimized if point[1] <= z2_u + numeric_epsilon)
    return _assemble(
        specs,
        utopian_min=(z1_u, z2_u),
        nadir_min=(z1_n, z2_n),
        epsilon=numeric_epsilon,
        tolerance=numeric_epsilon,
        method="approximate_front",
    )


def normalize_objectives(
    values: Sequence[float],
    reference: ReferencePoints,
    *,
    epsilon: float = 1e-12,
) -> tuple[float, ...]:
    """Map objective values to ``[0, 1]`` from the utopian point toward the nadir.

    A component whose utopian and nadir values coincide becomes ``0``.
    The scale is the minimization-space range, so ``0`` stays the individual
    best and ``1`` stays the worst value on the frontier.
    """

    numeric_epsilon = _non_negative_finite(epsilon, "epsilon")
    if len(values) != len(reference.objectives):
        raise ValueError("o vetor de objetivos não corresponde aos pontos de referência")

    normalized: list[float] = []
    for value, spec, utopian, nadir in zip(
        values, reference.objectives, reference.utopian, reference.nadir
    ):
        numeric_value = _finite_value(value)
        best = _negate_if_maximize(utopian, spec.direction)
        worst = _negate_if_maximize(nadir, spec.direction)
        observed = _negate_if_maximize(numeric_value, spec.direction)
        span = worst - best
        normalized.append(0.0 if span <= numeric_epsilon else (observed - best) / span)
    return tuple(normalized)


def euclidean_distance(left: Sequence[float], right: Sequence[float]) -> float:
    """Euclidean distance between two objective vectors of the same dimension."""

    if len(left) != len(right) or not left:
        raise ValueError("a distância euclidiana exige vetores de objetivos com a mesma dimensão")
    return dist(tuple(_finite_value(value) for value in left), tuple(_finite_value(value) for value in right))


def normalized_euclidean_distance(
    values: Sequence[float],
    anchor: Sequence[float],
    reference: ReferencePoints,
    *,
    epsilon: float = 1e-12,
) -> float:
    """Euclidean distance after mapping each objective to ``[0, 1]``.

    The scale is the same one used by :func:`normalize_objectives`: maximization
    is negated, and a null utopian–nadir range becomes ``0``.
    """

    return euclidean_distance(
        normalize_objectives(values, reference, epsilon=epsilon),
        normalize_objectives(anchor, reference, epsilon=epsilon),
    )


def _assemble(
    objectives: tuple[ObjectiveSpec, ...],
    *,
    utopian_min: tuple[float, float],
    nadir_min: tuple[float, float],
    epsilon: float,
    tolerance: float,
    method: str,
    extreme_best_first: object | None = None,
    extreme_best_second: object | None = None,
) -> ReferencePoints:
    slack = max(tolerance, epsilon)
    if nadir_min[0] < utopian_min[0] - slack or nadir_min[1] < utopian_min[1] - slack:
        raise ReferencePointError(
            "Inconsistência numérica: o ponto antiutópico ficou melhor que o utópico."
        )

    warnings: list[ReferenceWarning] = []
    if nadir_min[0] - utopian_min[0] <= epsilon or nadir_min[1] - utopian_min[1] <= epsilon:
        warnings.append(ReferenceWarning(_NON_CONFLICTING_CODE, _NON_CONFLICTING_MESSAGE))

    utopian = tuple(
        _negate_if_maximize(value, spec.direction)
        for value, spec in zip(utopian_min, objectives)
    )
    nadir = tuple(
        _negate_if_maximize(value, spec.direction)
        for value, spec in zip(nadir_min, objectives)
    )
    logger.info(
        "pontos de referência method=%s z1_U=%s z2_U=%s z1_N=%s z2_N=%s extreme_f1=%s extreme_f2=%s",
        method,
        utopian_min[0],
        utopian_min[1],
        nadir_min[0],
        nadir_min[1],
        extreme_best_first,
        extreme_best_second,
    )
    return ReferencePoints(
        objectives=objectives,
        utopian=utopian,
        nadir=nadir,
        warnings=tuple(warnings),
        method=method,
        extreme_best_first=extreme_best_first,
        extreme_best_second=extreme_best_second,
    )


def _solve_objective(
    solver: MonoobjectiveSolver,
    instance: object,
    objective_id: str,
    limits: Mapping[str, float],
    stage: str,
    parameters: Mapping[str, object],
) -> tuple[float, object | None]:
    result = solver.solve(
        instance,
        SolveRequest(
            objective=objective_id,
            objective_limits=dict(limits),
            parameters=parameters,
        ),
    )
    if result.status == "infeasible":
        raise ReferencePointError("problema inviável", stage=stage)
    if result.status not in {"optimal", "feasible"}:
        raise ReferencePointError("objetivo ilimitado ou sem solução finita", stage=stage)
    try:
        value = _finite_value(result.objective_values[objective_id])
    except (KeyError, TypeError, ValueError) as error:
        raise ReferencePointError(
            "objetivo ilimitado ou sem solução finita",
            stage=stage,
        ) from error
    return value, result.solution


def _two_objectives(objectives: Sequence[ObjectiveSpec]) -> tuple[ObjectiveSpec, ObjectiveSpec]:
    specs = tuple(objectives)
    if len(specs) != 2:
        raise ValueError(
            "O cálculo da solução utópica e da solução antiutópica exige exatamente 2 objetivos."
        )
    if not all(isinstance(spec, ObjectiveSpec) for spec in specs):
        raise ValueError("os objetivos devem ser ObjectiveSpec")
    if specs[0].id == specs[1].id:
        raise ValueError("os dois objetivos precisam ter identificadores diferentes")
    return specs[0], specs[1]


def _read_sample_value(sample: Mapping[str, float], objective_id: str) -> float:
    try:
        raw_value = sample[objective_id]
    except (KeyError, TypeError) as error:
        raise ValueError("cada solução precisa informar os dois objetivos") from error
    return _finite_value(raw_value)


def _finite_value(raw_value: object) -> float:
    if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
        raise ValueError("os valores de objetivo devem ser números reais finitos")
    value = float(raw_value)
    if not isfinite(value):
        raise ValueError("os valores de objetivo devem ser números reais finitos")
    return value


def _non_negative_finite(raw_value: object, name: str) -> float:
    if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
        raise ValueError(f"{name} deve ser um número finito maior ou igual a zero")
    value = float(raw_value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} deve ser um número finito maior ou igual a zero")
    return value


def _absolute_tolerance(anchor: float, delta: float) -> float:
    return delta * max(1.0, abs(anchor))


def _negate_if_maximize(value: float, direction: ObjectiveDirection) -> float:
    return -value if direction == "maximize" else value


def _as_mapping(objectives: Sequence[ObjectiveSpec], values: Sequence[float]) -> dict[str, float]:
    return {spec.id: value for spec, value in zip(objectives, values)}
