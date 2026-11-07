"""Monte Carlo robustness of a fixed bi-objective TSP front.

The procedure follows ``docs/algorithms/analise_robustez_tsp_biobjetivo.md``.
Routes stay fixed. Distance is deterministic and travel time on each used
arc is log-normal. Every route is scored on the same scenarios.

The nominal time is the mean of that log-normal by default, so the
simulation isolates variability. A median convention is available. A used
arc whose nominal time is zero stays at zero in every scenario: a
nonnegative time with mean zero cannot vary. Arc shocks can share a
regional factor and an optional global factor. This module does not
reoptimize the routes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite, sqrt
from numbers import Integral, Real
from typing import Literal, Mapping, Sequence

import numpy as np

from multiobjective_algorithms.hypervolume import hypervolume_2d

Convention = Literal["mean", "median"]
CV_GRID = (0.05, 0.10, 0.20, 0.30)
RHO_GRID = (0.0, 0.3, 0.6)
TOP_ARCS = 10
REFERENCE_SLACK = 1.05
CLOUD_SIZE = 120
SENSITIVITY_SCENARIOS = 1000


@dataclass(frozen=True)
class CriticalArc:
    source: int
    target: int
    nominal_time: float
    variance_share: float
    correlation: float | None


@dataclass(frozen=True)
class SolutionRobustness:
    distance: float
    nominal_time: float
    mean: float
    stdev: float
    coefficient_of_variation: float | None
    p50: float
    p90: float
    p95: float
    p99: float
    worst: float
    var: float
    cvar: float
    violation_probability: float | None
    p95_degradation: float | None
    mean_ci_low: float
    mean_ci_high: float
    win_frequency: float
    pareto_probability: float
    regret_mean: float
    regret_p95: float
    regret_max: float
    distance_regret: float
    hypervolume_contribution: float
    rank_frequencies: tuple[float, ...]
    box_min: float
    box_q1: float
    box_q3: float
    box_max: float
    critical_arcs: tuple[CriticalArc, ...]
    minmax_regret: float | None = None
    minmax_regret_p95: float | None = None


@dataclass(frozen=True)
class SensitivityPoint:
    cv: float
    rho: float
    mean: tuple[float, ...]
    p95: tuple[float, ...]
    cvar: tuple[float, ...]
    pareto_probability: tuple[float, ...]
    win_frequency: tuple[float, ...]


@dataclass(frozen=True)
class RobustnessParameters:
    scenarios: int
    seed: int
    cv: float
    rho: float
    rho0: float
    alpha: float
    convention: str
    time_limit: float | None
    region_method: str
    region_count: int
    sensitivity_scenarios: int | None


@dataclass(frozen=True)
class RobustnessReport:
    parameters: RobustnessParameters
    solutions: tuple[SolutionRobustness, ...]
    dominance: tuple[tuple[float, ...], ...]
    cloud_times: tuple[tuple[float, ...], ...]
    reference_distance: float
    reference_time: float
    mean_hypervolume: float
    stdev_hypervolume: float
    sensitivity_by_cv: tuple[SensitivityPoint, ...]
    sensitivity_by_rho: tuple[SensitivityPoint, ...]
    ranking_inversion_cv: float | None
    frontier_loss_cv: float | None
    deterministic_zero_arcs: int


@dataclass(frozen=True)
class _Simulation:
    times: np.ndarray
    distance: np.ndarray
    nominal_time: np.ndarray
    arcs: tuple[tuple[int, int], ...]
    route_arc_indices: tuple[np.ndarray, ...]
    arc_nominal: np.ndarray
    arc_times: np.ndarray | None
    region_method: str
    region_count: int
    deterministic_zero_arcs: int


def analyze_robustness(
    routes: Sequence[Sequence[int]],
    distance: Sequence[Sequence[float]],
    nominal_time: Sequence[Sequence[float]],
    *,
    coordinates: Sequence[Sequence[float]] | None = None,
    cv: float = 0.2,
    rho: float = 0.3,
    rho0: float = 0.0,
    scenarios: int = 5000,
    seed: int = 42,
    alpha: float = 0.95,
    time_limit: float | None = None,
    convention: Convention = "mean",
    include_sensitivity: bool = False,
    sensitivity_scenarios: int = SENSITIVITY_SCENARIOS,
    cloud_size: int = CLOUD_SIZE,
) -> RobustnessReport:
    """Evaluate fixed routes under shared log-normal time scenarios.

    ``routes`` use 1-based city ids. A repeated first city at the end is the
    return to the depot and is accepted. ``distance`` and ``nominal_time``
    are square matrices in that same city order.
    """

    cv_value = _non_negative(cv, "cv")
    rho_value = _correlation(rho, "rho")
    rho0_value = _correlation(rho0, "rho0")
    if rho_value + rho0_value >= 1:
        raise ValueError("rho e rho0 devem ser não negativos e somar menos de 1")
    scenario_count = _scenario_count(scenarios)
    seed_value = _seed(seed)
    alpha_value = _alpha(alpha)
    convention_value = _convention(convention)
    limit = None if time_limit is None else _finite(time_limit, "time_limit")
    cloud_count = _cloud_count(cloud_size, scenario_count)
    sensitivity_count = _scenario_count(sensitivity_scenarios) if include_sensitivity else None

    simulation = _simulate(
        routes,
        distance,
        nominal_time,
        coordinates=coordinates,
        cv=cv_value,
        rho=rho_value,
        rho0=rho0_value,
        scenarios=scenario_count,
        seed=seed_value,
        convention=convention_value,
        keep_arc_samples=True,
    )
    measured = _measure(
        simulation,
        alpha=alpha_value,
        time_limit=limit,
        cv=cv_value,
    )
    cloud = _cloud(simulation.times, cloud_count)
    by_cv: tuple[SensitivityPoint, ...] = ()
    by_rho: tuple[SensitivityPoint, ...] = ()
    inversion: float | None = None
    frontier_loss: float | None = None
    if include_sensitivity:
        assert sensitivity_count is not None
        by_cv = tuple(
            _sensitivity_point(
                routes,
                distance,
                nominal_time,
                coordinates=coordinates,
                cv=point_cv,
                rho=rho_value,
                rho0=rho0_value,
                scenarios=sensitivity_count,
                seed=_sensitivity_seed(seed_value, 1, index),
                alpha=alpha_value,
                convention=convention_value,
            )
            for index, point_cv in enumerate(_cv_grid(cv_value))
        )
        by_rho = tuple(
            _sensitivity_point(
                routes,
                distance,
                nominal_time,
                coordinates=coordinates,
                cv=cv_value,
                rho=point_rho,
                rho0=rho0_value,
                scenarios=sensitivity_count,
                seed=_sensitivity_seed(seed_value, 2, index),
                alpha=alpha_value,
                convention=convention_value,
            )
            for index, point_rho in enumerate(_rho_grid(rho_value, rho0_value))
        )
        inversion = ranking_inversion_cv(simulation.nominal_time, by_cv)
        frontier_loss = frontier_loss_cv(by_cv)

    return RobustnessReport(
        parameters=RobustnessParameters(
            scenarios=scenario_count,
            seed=seed_value,
            cv=cv_value,
            rho=rho_value,
            rho0=rho0_value,
            alpha=alpha_value,
            convention=convention_value,
            time_limit=limit,
            region_method=simulation.region_method,
            region_count=simulation.region_count,
            sensitivity_scenarios=sensitivity_count if include_sensitivity else None,
        ),
        solutions=measured[0],
        dominance=measured[1],
        cloud_times=cloud,
        reference_distance=measured[2],
        reference_time=measured[3],
        mean_hypervolume=measured[4],
        stdev_hypervolume=measured[5],
        sensitivity_by_cv=by_cv,
        sensitivity_by_rho=by_rho,
        ranking_inversion_cv=inversion,
        frontier_loss_cv=frontier_loss,
        deterministic_zero_arcs=simulation.deterministic_zero_arcs,
    )


def ranking_inversion_cv(
    nominal_time: Sequence[float],
    points: Sequence[SensitivityPoint],
) -> float | None:
    """Smallest CV whose mean-time order differs from the nominal order."""

    if len(nominal_time) < 2:
        return None
    nominal_order = tuple(np.argsort(np.asarray(nominal_time, dtype=float), kind="mergesort"))
    for point in sorted(points, key=lambda item: item.cv):
        order = tuple(np.argsort(np.asarray(point.mean, dtype=float), kind="mergesort"))
        if order != nominal_order:
            return point.cv
    return None


def frontier_loss_cv(
    points: Sequence[SensitivityPoint],
    *,
    stable: float = 0.95,
    lost: float = 0.5,
) -> float | None:
    """Smallest CV where a solution that was robustly efficient stops being so.

    A solution counts as robustly efficient when its Pareto probability is at
    least ``stable`` on the smallest CV. It is lost when that probability
    later falls below ``lost``.
    """

    ordered = tuple(sorted(points, key=lambda item: item.cv))
    if len(ordered) < 2 or not ordered[0].pareto_probability:
        return None
    watched = [
        index
        for index, probability in enumerate(ordered[0].pareto_probability)
        if probability >= stable
    ]
    if not watched:
        return None
    for point in ordered[1:]:
        if any(point.pareto_probability[index] < lost for index in watched):
            return point.cv
    return None


@dataclass(frozen=True)
class NormalizedMinMaxRegret:
    distance_ratio: float | None
    time_ratio: float | None
    time_p95_ratio: float | None
    score: float | None
    score_p95: float | None


def normalized_minmax_regret(
    distance: Sequence[float],
    mean_time: Sequence[float],
    regret_mean: Sequence[float],
    regret_p95: Sequence[float],
) -> tuple[NormalizedMinMaxRegret, ...]:
    """Worst relative regret between distance and time for each solution.

    Distance uses ``(D_k - min D) / min D``. Time divides the mean regret,
    and separately the P95 regret, by the smallest mean time. Each score is
    the larger of the distance ratio and that time ratio. A zero reference
    makes the ratio undefined when the excess is positive. The preferred
    solution is the one with the smaller score.
    """

    count = len(distance)
    if not count or len(mean_time) != count or len(regret_mean) != count or len(regret_p95) != count:
        raise ValueError("as métricas de min-max regret precisam ter o mesmo tamanho e ao menos uma solução")
    distances = [_finite(value, "distância") for value in distance]
    means = [_finite(value, "média") for value in mean_time]
    regrets = [_finite(value, "regret médio") for value in regret_mean]
    regrets_p95 = [_finite(value, "regret P95") for value in regret_p95]
    if any(value < 0 for value in distances + regrets + regrets_p95):
        raise ValueError("distância e regrets do min-max precisam ser não negativos")
    distance_reference = min(distances)
    time_reference = min(means)
    rows: list[NormalizedMinMaxRegret] = []
    for index in range(count):
        distance_ratio = _relative_excess(distances[index] - distance_reference, distance_reference)
        time_ratio = _relative_excess(regrets[index], time_reference)
        time_p95_ratio = _relative_excess(regrets_p95[index], time_reference)
        rows.append(
            NormalizedMinMaxRegret(
                distance_ratio=distance_ratio,
                time_ratio=time_ratio,
                time_p95_ratio=time_p95_ratio,
                score=_worst_ratio(distance_ratio, time_ratio),
                score_p95=_worst_ratio(distance_ratio, time_p95_ratio),
            )
        )
    return tuple(rows)


def _relative_excess(excess: float, reference: float) -> float | None:
    if reference > 0:
        return excess / reference
    if excess == 0:
        return 0.0
    return None


def _worst_ratio(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return max(left, right)


def _simulate(
    routes: Sequence[Sequence[int]],
    distance: Sequence[Sequence[float]],
    nominal_time: Sequence[Sequence[float]],
    *,
    coordinates: Sequence[Sequence[float]] | None,
    cv: float,
    rho: float,
    rho0: float,
    scenarios: int,
    seed: int,
    convention: str,
    keep_arc_samples: bool,
) -> _Simulation:
    if isinstance(routes, (str, bytes)) or not isinstance(routes, Sequence) or not routes:
        raise ValueError("não há rotas para avaliar")
    time_matrix = _matrix(nominal_time, "a matriz de tempo")
    distance_matrix = _matrix(distance, "a matriz de distância")
    if time_matrix.shape != distance_matrix.shape:
        raise ValueError("as matrizes de tempo e distância precisam ter o mesmo tamanho")
    if np.any(time_matrix < 0):
        raise ValueError("a matriz de tempo não pode conter valores negativos")
    if np.any(distance_matrix < 0):
        raise ValueError("a matriz de distância não pode conter valores negativos")
    node_count = int(time_matrix.shape[0])
    points = _coordinates(coordinates, node_count)

    cycles = [_cycle_nodes(route, node_count) for route in routes]
    arc_lists = [
        [(cycle[index], cycle[(index + 1) % len(cycle)]) for index in range(len(cycle))]
        for cycle in cycles
    ]
    arcs = tuple(sorted({arc for route_arcs in arc_lists for arc in route_arcs}))
    arc_index = {arc: index for index, arc in enumerate(arcs)}
    pairs = np.asarray(arcs, dtype=int)
    used_time = time_matrix[pairs[:, 0] - 1, pairs[:, 1] - 1]
    positive = used_time > 0

    solution_count = len(arc_lists)
    incidence = np.zeros((solution_count, len(arcs)), dtype=float)
    route_arc_indices: list[np.ndarray] = []
    for solution_index, route_arcs in enumerate(arc_lists):
        indices = np.array([arc_index[arc] for arc in route_arcs], dtype=int)
        incidence[solution_index, indices] = 1.0
        route_arc_indices.append(indices)

    sigma = np.zeros(len(arcs), dtype=float)
    mu = np.zeros(len(arcs), dtype=float)
    if cv > 0 and np.any(positive):
        sigma_value = float(np.sqrt(np.log1p(cv * cv)))
        sigma[positive] = sigma_value
        logged = np.log(used_time[positive])
        if convention == "mean":
            mu[positive] = logged - 0.5 * sigma_value * sigma_value
        else:
            mu[positive] = logged

    region_ids, region_method = _regions(arcs, points, node_count, seed)
    arc_times = _sample_arc_times(
        mu,
        sigma,
        region_ids,
        scenarios=scenarios,
        seed=seed,
        rho=rho,
        rho0=rho0,
        nominal=used_time,
    )
    times = arc_times @ incidence.T
    nominal = incidence @ used_time
    distance_of_arcs = np.array(
        [distance_matrix[source - 1, target - 1] for source, target in arcs],
        dtype=float,
    )
    return _Simulation(
        times=times,
        distance=incidence @ distance_of_arcs,
        nominal_time=nominal,
        arcs=arcs,
        route_arc_indices=tuple(route_arc_indices),
        arc_nominal=used_time,
        arc_times=arc_times if keep_arc_samples else None,
        region_method=region_method,
        region_count=int(len(np.unique(region_ids))),
        deterministic_zero_arcs=int(np.count_nonzero(~positive)),
    )


def _sample_arc_times(
    mu: np.ndarray,
    sigma: np.ndarray,
    region_ids: np.ndarray,
    *,
    scenarios: int,
    seed: int,
    rho: float,
    rho0: float,
    nominal: np.ndarray,
) -> np.ndarray:
    if np.all(sigma == 0):
        return np.broadcast_to(nominal, (scenarios, nominal.size)).copy()
    generator = np.random.default_rng(seed)
    compact_regions, inverse = np.unique(region_ids, return_inverse=True)
    global_factor = generator.standard_normal((scenarios, 1))
    regional = generator.standard_normal((scenarios, len(compact_regions)))[:, inverse]
    idiosyncratic = generator.standard_normal((scenarios, nominal.size))
    shocks = (
        sqrt(rho0) * global_factor
        + sqrt(rho) * regional
        + sqrt(1.0 - rho0 - rho) * idiosyncratic
    )
    sampled = np.exp(mu + sigma * shocks)
    sampled[:, nominal <= 0] = 0.0
    return sampled


def _measure(
    simulation: _Simulation,
    *,
    alpha: float,
    time_limit: float | None,
    cv: float,
) -> tuple[
    tuple[SolutionRobustness, ...],
    tuple[tuple[float, ...], ...],
    float,
    float,
    float,
    float,
]:
    times = simulation.times
    scenarios, solution_count = times.shape
    distance = simulation.distance
    nominal = simulation.nominal_time
    nondominated = _nondominated_mask(distance, times)
    wins = _win_mask(times)
    ranks = 1 + np.sum(times[:, None, :] < times[:, :, None], axis=2)
    best_time = times.min(axis=1, keepdims=True)
    regret = times - best_time
    dominance = _dominance_probabilities(distance, times)
    reference_distance, reference_time = _hypervolume_reference(distance, times)
    hypervolume, contributions = _hypervolume_contributions(
        distance,
        times,
        nondominated,
        (reference_distance, reference_time),
    )
    minimum_distance = float(distance.min())
    solutions: list[SolutionRobustness] = []
    for index in range(solution_count):
        column = times[:, index]
        mean = float(column.mean())
        stdev = 0.0 if scenarios == 1 else float(column.std(ddof=1))
        p95 = float(np.quantile(column, 0.95))
        nominal_time = float(nominal[index])
        half_width = 1.96 * stdev / sqrt(scenarios)
        rank_counts = np.bincount(ranks[:, index], minlength=solution_count + 1)[1:]
        solutions.append(
            SolutionRobustness(
                distance=float(distance[index]),
                nominal_time=nominal_time,
                mean=mean,
                stdev=stdev,
                coefficient_of_variation=None if mean == 0 else stdev / mean,
                p50=float(np.quantile(column, 0.50)),
                p90=float(np.quantile(column, 0.90)),
                p95=p95,
                p99=float(np.quantile(column, 0.99)),
                worst=float(column.max()),
                var=float(np.quantile(column, alpha)),
                cvar=_cvar(column, alpha),
                violation_probability=(
                    None if time_limit is None else float(np.mean(column > time_limit))
                ),
                p95_degradation=None if nominal_time == 0 else (p95 - nominal_time) / nominal_time,
                mean_ci_low=mean - half_width,
                mean_ci_high=mean + half_width,
                win_frequency=float(wins[:, index].mean()),
                pareto_probability=float(nondominated[:, index].mean()),
                regret_mean=float(regret[:, index].mean()),
                regret_p95=float(np.quantile(regret[:, index], 0.95)),
                regret_max=float(regret[:, index].max()),
                distance_regret=float(distance[index] - minimum_distance),
                hypervolume_contribution=float(contributions[:, index].mean()),
                rank_frequencies=tuple(float(count / scenarios) for count in rank_counts),
                box_min=float(column.min()),
                box_q1=float(np.quantile(column, 0.25)),
                box_q3=float(np.quantile(column, 0.75)),
                box_max=float(column.max()),
                critical_arcs=_critical_arcs(simulation, index, cv),
            )
        )
    scored = normalized_minmax_regret(
        [item.distance for item in solutions],
        [item.mean for item in solutions],
        [item.regret_mean for item in solutions],
        [item.regret_p95 for item in solutions],
    )
    solutions = [
        replace(item, minmax_regret=score.score, minmax_regret_p95=score.score_p95)
        for item, score in zip(solutions, scored, strict=True)
    ]
    return (
        tuple(solutions),
        tuple(tuple(float(value) for value in row) for row in dominance),
        reference_distance,
        reference_time,
        float(hypervolume.mean()),
        0.0 if scenarios == 1 else float(hypervolume.std(ddof=1)),
    )


def _sensitivity_point(
    routes: Sequence[Sequence[int]],
    distance: Sequence[Sequence[float]],
    nominal_time: Sequence[Sequence[float]],
    *,
    coordinates: Sequence[Sequence[float]] | None,
    cv: float,
    rho: float,
    rho0: float,
    scenarios: int,
    seed: int,
    alpha: float,
    convention: str,
) -> SensitivityPoint:
    simulation = _simulate(
        routes,
        distance,
        nominal_time,
        coordinates=coordinates,
        cv=cv,
        rho=rho,
        rho0=rho0,
        scenarios=scenarios,
        seed=seed,
        convention=convention,
        keep_arc_samples=False,
    )
    times = simulation.times
    nondominated = _nondominated_mask(simulation.distance, times)
    wins = _win_mask(times)
    return SensitivityPoint(
        cv=cv,
        rho=rho,
        mean=tuple(float(value) for value in times.mean(axis=0)),
        p95=tuple(float(value) for value in np.quantile(times, 0.95, axis=0)),
        cvar=tuple(_cvar(times[:, index], alpha) for index in range(times.shape[1])),
        pareto_probability=tuple(float(value) for value in nondominated.mean(axis=0)),
        win_frequency=tuple(float(value) for value in wins.mean(axis=0)),
    )


def _critical_arcs(simulation: _Simulation, solution_index: int, cv: float) -> tuple[CriticalArc, ...]:
    indices = simulation.route_arc_indices[solution_index]
    nominal = simulation.arc_nominal[indices]
    eligible = np.flatnonzero(nominal > 0)
    if eligible.size == 0:
        return ()
    chosen = nominal[eligible]
    variance = (cv * chosen) ** 2
    total = float(variance.sum())
    shares = variance / total if total > 0 else np.full(chosen.shape, 1 / chosen.size)
    samples = simulation.arc_times
    route_time = simulation.times[:, solution_index]
    ranked: list[tuple[float, float, int]] = []
    for offset, position in enumerate(eligible):
        arc_index = int(indices[int(position)])
        correlation = None if samples is None else _correlation_coefficient(samples[:, arc_index], route_time)
        score = -1.0 if correlation is None else abs(correlation)
        ranked.append((score, float(shares[offset]), int(position)))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    arcs: list[CriticalArc] = []
    for _, share, position in ranked[:TOP_ARCS]:
        source, target = simulation.arcs[int(indices[position])]
        correlation = None if samples is None else _correlation_coefficient(samples[:, int(indices[position])], route_time)
        arcs.append(
            CriticalArc(
                source=source,
                target=target,
                nominal_time=float(nominal[position]),
                variance_share=share,
                correlation=correlation,
            )
        )
    return tuple(arcs)


def _correlation_coefficient(left: np.ndarray, right: np.ndarray) -> float | None:
    left_centered = left - left.mean()
    right_centered = right - right.mean()
    denominator = sqrt(float(left_centered @ left_centered) * float(right_centered @ right_centered))
    if denominator == 0:
        return None
    return float((left_centered @ right_centered) / denominator)


def _cvar(column: np.ndarray, alpha: float) -> float:
    cutoff = float(np.quantile(column, alpha))
    tail = column[column > cutoff]
    if tail.size == 0:
        return cutoff
    return float(tail.mean())


def _win_mask(times: np.ndarray) -> np.ndarray:
    best = times.min(axis=1, keepdims=True)
    return np.isclose(times, best, rtol=1e-8, atol=1e-8)


def _nondominated_mask(distance: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Scenario-wise Pareto mask for minimization of fixed distance and sampled time."""

    order = np.argsort(distance, kind="mergesort")
    ordered_distance = distance[order]
    ordered_times = times[:, order]
    scenarios, solution_count = ordered_times.shape
    ordered_mask = np.zeros((scenarios, solution_count), dtype=bool)
    best_previous = np.full(scenarios, np.inf)
    start = 0
    while start < solution_count:
        end = start + 1
        while end < solution_count and ordered_distance[end] == ordered_distance[start]:
            end += 1
        group = ordered_times[:, start:end]
        group_min = group.min(axis=1)
        ordered_mask[:, start:end] = (group < best_previous[:, None]) & (group == group_min[:, None])
        best_previous = np.minimum(best_previous, group_min)
        start = end
    mask = np.empty_like(ordered_mask)
    mask[:, order] = ordered_mask
    return mask


def _dominance_probabilities(distance: np.ndarray, times: np.ndarray) -> np.ndarray:
    solution_count = distance.size
    scenarios = times.shape[0]
    accumulator = np.zeros((solution_count, solution_count), dtype=np.int32)
    chunk = max(1, min(scenarios, 2_000_000 // max(solution_count * solution_count, 1)))
    distance_left = distance[:, None]
    distance_right = distance[None, :]
    distance_no_worse = distance_left <= distance_right
    distance_better = distance_left < distance_right
    for start in range(0, scenarios, chunk):
        block = times[start : start + chunk]
        time_no_worse = block[:, :, None] <= block[:, None, :]
        time_better = block[:, :, None] < block[:, None, :]
        dominates = distance_no_worse & time_no_worse & (distance_better | time_better)
        accumulator += dominates.sum(axis=0, dtype=np.int32)
    return accumulator / scenarios


def _hypervolume_reference(distance: np.ndarray, times: np.ndarray) -> tuple[float, float]:
    return (
        float(np.max(distance) * REFERENCE_SLACK),
        float(np.max(times) * REFERENCE_SLACK),
    )


def _hypervolume_contributions(
    distance: np.ndarray,
    times: np.ndarray,
    nondominated: np.ndarray,
    reference: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    scenarios, solution_count = times.shape
    total = np.empty(scenarios, dtype=float)
    contributions = np.zeros((scenarios, solution_count), dtype=float)
    for scenario in range(scenarios):
        members = np.flatnonzero(nondominated[scenario])
        points = [(float(distance[index]), float(times[scenario, index])) for index in members]
        area = hypervolume_2d(points, reference)
        total[scenario] = area
        if members.size == 1:
            contributions[scenario, members[0]] = area
            continue
        for position, member in enumerate(members):
            reduced = [point for index, point in enumerate(points) if index != position]
            contributions[scenario, member] = max(0.0, area - hypervolume_2d(reduced, reference))
    return total, contributions


def _cloud(times: np.ndarray, size: int) -> tuple[tuple[float, ...], ...]:
    if size <= 0:
        return ()
    indices = np.unique(np.linspace(0, times.shape[0] - 1, size, dtype=int))
    return tuple(tuple(float(value) for value in row) for row in times[indices])


def _regions(
    arcs: Sequence[tuple[int, int]],
    coordinates: np.ndarray | None,
    node_count: int,
    seed: int,
) -> tuple[np.ndarray, str]:
    if coordinates is None:
        return np.zeros(len(arcs), dtype=int), "single"
    midpoints = np.array(
        [
            (
                (coordinates[source - 1, 0] + coordinates[target - 1, 0]) / 2,
                (coordinates[source - 1, 1] + coordinates[target - 1, 1]) / 2,
            )
            for source, target in arcs
        ],
        dtype=float,
    )
    region_count = max(1, min(8, int(round(sqrt(node_count)))))
    return _kmeans_labels(midpoints, region_count, seed), "kmeans_midpoint"


def _kmeans_labels(points: np.ndarray, cluster_count: int, seed: int) -> np.ndarray:
    count = points.shape[0]
    if cluster_count <= 1 or count <= 1:
        return np.zeros(count, dtype=int)
    cluster_count = min(cluster_count, count)
    generator = np.random.default_rng(seed)
    centers = np.empty((cluster_count, points.shape[1]), dtype=float)
    centers[0] = points[int(generator.integers(count))]
    closest = np.full(count, np.inf)
    for cluster in range(1, cluster_count):
        closest = np.minimum(closest, ((points - centers[cluster - 1]) ** 2).sum(axis=1))
        total = float(closest.sum())
        if total <= 0:
            centers[cluster:] = centers[cluster - 1]
            break
        centers[cluster] = points[int(generator.choice(count, p=closest / total))]
    labels = np.zeros(count, dtype=int)
    for _ in range(25):
        distances = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        updated = distances.argmin(axis=1)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for cluster in range(cluster_count):
            members = points[labels == cluster]
            if len(members):
                centers[cluster] = members.mean(axis=0)
            else:
                centers[cluster] = points[int(generator.integers(count))]
    return labels


def _cycle_nodes(route: Sequence[int], node_count: int) -> list[int]:
    if isinstance(route, (str, bytes)) or not isinstance(route, Sequence):
        raise ValueError("cada rota deve ser uma sequência de cidades")
    nodes: list[int] = []
    for value in route:
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError("os identificadores de cidade devem ser inteiros")
        nodes.append(int(value))
    if len(nodes) >= 2 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    if sorted(nodes) != list(range(1, node_count + 1)):
        raise ValueError("cada rota deve visitar cada cidade exatamente uma vez")
    return nodes


def _matrix(values: Sequence[Sequence[float]], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[0] != array.shape[1] or array.shape[0] < 2:
        raise ValueError(f"{name} precisa ser quadrada e ter ao menos duas cidades")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} precisa conter apenas valores finitos")
    return array


def _coordinates(
    coordinates: Sequence[Sequence[float]] | None,
    node_count: int,
) -> np.ndarray | None:
    if coordinates is None:
        return None
    points = np.asarray(coordinates, dtype=float)
    if points.shape != (node_count, 2) or not np.isfinite(points).all():
        raise ValueError("as coordenadas precisam ser um par finito por cidade")
    return points


def _cv_grid(cv: float) -> tuple[float, ...]:
    return tuple(sorted({*CV_GRID, cv}))


def _rho_grid(rho: float, rho0: float) -> tuple[float, ...]:
    values = [value for value in (*RHO_GRID, rho) if value >= 0 and value + rho0 < 1]
    return tuple(sorted(set(values)))


def _sensitivity_seed(seed: int, family: int, index: int) -> int:
    sequence = np.random.SeedSequence([seed, family, index])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


def _cloud_count(value: object, scenarios: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 0:
        raise ValueError("cloud_size deve ser um inteiro maior ou igual a zero")
    return min(int(value), scenarios)


def _scenario_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or not 1 <= int(value) <= 20_000:
        raise ValueError("scenarios deve ser um inteiro entre 1 e 20000")
    return int(value)


def _seed(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError("seed deve ser um inteiro")
    return int(value)


def _alpha(value: object) -> float:
    number = _finite(value, "alpha")
    if not 0 < number < 1:
        raise ValueError("alpha deve estar estritamente entre 0 e 1")
    return number


def _convention(value: object) -> Convention:
    if value not in {"mean", "median"}:
        raise ValueError("convention deve ser 'mean' ou 'median'")
    return value


def _correlation(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0:
        raise ValueError(f"{name} deve ser maior ou igual a zero")
    return number


def _non_negative(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0:
        raise ValueError(f"{name} deve ser maior ou igual a zero")
    return number


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} deve ser um número finito")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} deve ser um número finito")
    return number


def parameters_as_mapping(parameters: RobustnessParameters) -> Mapping[str, object]:
    return {
        "scenarios": parameters.scenarios,
        "seed": parameters.seed,
        "cv": parameters.cv,
        "rho": parameters.rho,
        "rho0": parameters.rho0,
        "alpha": parameters.alpha,
        "convention": parameters.convention,
        "time_limit": parameters.time_limit,
        "region_method": parameters.region_method,
        "region_count": parameters.region_count,
        "sensitivity_scenarios": parameters.sensitivity_scenarios,
    }
