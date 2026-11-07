import numpy as np
import pytest

from multiobjective_algorithms.robustness import (
    SensitivityPoint,
    analyze_robustness,
    frontier_loss_cv,
    normalized_minmax_regret,
    ranking_inversion_cv,
)


def _blank(size: int) -> list[list[float]]:
    return [[0.0] * size for _ in range(size)]


def _paint(matrix: list[list[float]], route: list[int], costs: list[float]) -> None:
    for (source, target), cost in zip(zip(route, route[1:]), costs):
        matrix[source - 1][target - 1] = cost


def _dominated_pair() -> tuple[list[list[float]], list[list[float]], list[list[int]]]:
    time = _blank(4)
    distance = _blank(4)
    short = [1, 2, 3, 4, 1]
    long = [1, 2, 4, 3, 1]
    _paint(time, short, [1, 1, 1, 1])
    _paint(distance, short, [1, 1, 1, 1])
    _paint(time, long, [1, 3, 3, 3])
    _paint(distance, long, [1, 2, 2, 2])
    return time, distance, [short, long]


def _tradeoff_pair() -> tuple[list[list[float]], list[list[float]], list[list[int]]]:
    time = _blank(4)
    distance = _blank(4)
    near = [1, 2, 3, 4, 1]
    far = [1, 4, 3, 2, 1]
    _paint(time, near, [2.5, 2.5, 2.5, 2.5])
    _paint(distance, near, [1, 1, 1, 1])
    _paint(time, far, [1.5, 1.5, 1.5, 1.5])
    _paint(distance, far, [2, 2, 2, 2])
    return time, distance, [near, far]


def test_zero_variability_reproduces_nominal_times_and_dominance() -> None:
    time, distance, routes = _dominated_pair()

    report = analyze_robustness(
        routes,
        distance,
        time,
        cv=0,
        rho=0,
        rho0=0,
        scenarios=32,
        seed=3,
        include_sensitivity=False,
    )

    short, long = report.solutions
    assert short.distance == pytest.approx(4)
    assert short.nominal_time == pytest.approx(4)
    assert long.distance == pytest.approx(7)
    assert long.nominal_time == pytest.approx(10)
    assert short.mean == pytest.approx(short.nominal_time)
    assert short.stdev == 0
    assert short.p95_degradation == pytest.approx(0)
    assert short.pareto_probability == pytest.approx(1)
    assert long.pareto_probability == pytest.approx(0)
    assert report.dominance[0][1] == pytest.approx(1)
    assert report.dominance[1][0] == pytest.approx(0)
    assert report.dominance[0][0] == pytest.approx(0)
    assert short.win_frequency == pytest.approx(1)
    assert long.win_frequency == pytest.approx(0)
    assert short.regret_mean == pytest.approx(0)
    assert long.regret_mean == pytest.approx(6)
    assert short.distance_regret == pytest.approx(0)
    assert long.distance_regret == pytest.approx(3)
    assert short.rank_frequencies == pytest.approx((1, 0))
    assert long.rank_frequencies == pytest.approx((0, 1))
    assert short.minmax_regret == pytest.approx(0)
    assert short.minmax_regret_p95 == pytest.approx(0)
    assert long.minmax_regret == pytest.approx(1.5)
    assert long.minmax_regret_p95 == pytest.approx(1.5)
    assert report.mean_hypervolume == pytest.approx(21.775)
    assert short.hypervolume_contribution == pytest.approx(21.775)
    assert long.hypervolume_contribution == pytest.approx(0)
    assert sum(arc.variance_share for arc in short.critical_arcs) == pytest.approx(1)
    assert all(arc.correlation is None for arc in short.critical_arcs)


def test_tradeoff_keeps_both_routes_efficient_when_time_is_certain() -> None:
    time, distance, routes = _tradeoff_pair()

    report = analyze_robustness(
        routes,
        distance,
        time,
        cv=0,
        rho=0,
        rho0=0,
        scenarios=16,
        seed=1,
    )

    near, far = report.solutions
    assert near.nominal_time == pytest.approx(10)
    assert near.distance == pytest.approx(4)
    assert far.nominal_time == pytest.approx(6)
    assert far.distance == pytest.approx(8)
    assert near.pareto_probability == pytest.approx(1)
    assert far.pareto_probability == pytest.approx(1)
    assert report.dominance[0][1] == pytest.approx(0)
    assert report.dominance[1][0] == pytest.approx(0)
    assert far.win_frequency == pytest.approx(1)
    assert near.regret_mean == pytest.approx(4)
    assert far.regret_mean == pytest.approx(0)
    assert report.mean_hypervolume == pytest.approx(3.8)
    assert near.hypervolume_contribution == pytest.approx(2.0)
    assert far.hypervolume_contribution == pytest.approx(1.6)
    assert report.reference_distance == pytest.approx(8.4)
    assert report.reference_time == pytest.approx(10.5)


def test_open_and_closed_routes_have_the_same_cost() -> None:
    time, distance, routes = _tradeoff_pair()
    closed = analyze_robustness(routes[:1], distance, time, cv=0, rho=0, rho0=0, scenarios=4, seed=1)
    opened = analyze_robustness(
        [routes[0][:-1]],
        distance,
        time,
        cv=0,
        rho=0,
        rho0=0,
        scenarios=4,
        seed=1,
    )

    assert opened.solutions[0].distance == pytest.approx(closed.solutions[0].distance)
    assert opened.solutions[0].nominal_time == pytest.approx(closed.solutions[0].nominal_time)


def test_mean_convention_stays_near_the_nominal_time() -> None:
    time, distance, routes = _dominated_pair()

    report = analyze_robustness(
        routes[:1],
        distance,
        time,
        cv=0.25,
        rho=0,
        rho0=0,
        scenarios=4000,
        seed=7,
    )

    solution = report.solutions[0]
    assert abs(solution.mean - solution.nominal_time) / solution.nominal_time < 0.015


def test_median_convention_raises_the_expected_time() -> None:
    time, distance, routes = _dominated_pair()

    report = analyze_robustness(
        routes[:1],
        distance,
        time,
        cv=0.5,
        rho=0,
        rho0=0,
        scenarios=4000,
        seed=9,
        convention="median",
    )

    solution = report.solutions[0]
    assert solution.mean > solution.nominal_time * 1.02


def test_regional_correlation_increases_route_variance() -> None:
    size = 6
    time = _blank(size)
    distance = _blank(size)
    route = list(range(1, size + 1)) + [1]
    _paint(time, route, [2] * size)
    _paint(distance, route, [1] * size)
    coordinates = [(float(index), 0.0) for index in range(size)]
    common = dict(cv=0.5, rho0=0.0, scenarios=2000, seed=11, convention="mean")

    independent = analyze_robustness([route], distance, time, coordinates=coordinates, rho=0, **common)
    correlated = analyze_robustness([route], distance, time, coordinates=coordinates, rho=0.8, **common)

    assert correlated.parameters.region_method == "kmeans_midpoint"
    assert correlated.solutions[0].stdev > independent.solutions[0].stdev * 1.5


def test_identical_routes_share_every_scenario() -> None:
    time, distance, routes = _tradeoff_pair()

    report = analyze_robustness(
        [routes[0], routes[0]],
        distance,
        time,
        cv=0.3,
        rho=0.2,
        rho0=0.1,
        scenarios=200,
        seed=5,
    )

    assert report.solutions[0].win_frequency == pytest.approx(1)
    assert report.solutions[1].win_frequency == pytest.approx(1)
    assert report.solutions[0].regret_max == pytest.approx(0)
    assert report.cloud_times
    assert all(row[0] == pytest.approx(row[1]) for row in report.cloud_times)


def test_same_seed_reproduces_the_sample() -> None:
    time, distance, routes = _tradeoff_pair()
    kwargs = dict(cv=0.2, rho=0.3, rho0=0.0, scenarios=80, seed=15)

    first = analyze_robustness(routes, distance, time, **kwargs)
    second = analyze_robustness(routes, distance, time, **kwargs)

    assert first.solutions[0].mean == pytest.approx(second.solutions[0].mean)
    assert first.solutions[1].p95 == pytest.approx(second.solutions[1].p95)
    assert np.array(first.cloud_times) == pytest.approx(np.array(second.cloud_times))


def test_time_limit_counts_violations_when_times_are_certain() -> None:
    time, distance, routes = _dominated_pair()

    below = analyze_robustness(
        routes[:1], distance, time, cv=0, rho=0, rho0=0, scenarios=8, seed=1, time_limit=3
    )
    above = analyze_robustness(
        routes[:1], distance, time, cv=0, rho=0, rho0=0, scenarios=8, seed=1, time_limit=5
    )

    assert below.solutions[0].violation_probability == pytest.approx(1)
    assert above.solutions[0].violation_probability == pytest.approx(0)


def test_sensitivity_grid_follows_the_requested_cv_and_rho() -> None:
    time, distance, routes = _tradeoff_pair()

    report = analyze_robustness(
        routes,
        distance,
        time,
        cv=0.2,
        rho=0.3,
        rho0=0,
        scenarios=12,
        sensitivity_scenarios=12,
        seed=2,
        include_sensitivity=True,
    )

    assert [point.cv for point in report.sensitivity_by_cv] == [0.05, 0.10, 0.20, 0.30]
    assert [point.rho for point in report.sensitivity_by_rho] == [0.0, 0.3, 0.6]
    assert all(len(point.pareto_probability) == 2 for point in report.sensitivity_by_cv)
    assert report.parameters.sensitivity_scenarios == 12
    assert report.parameters.region_method == "single"
    assert report.parameters.region_count == 1


def test_ranking_and_frontier_loss_use_the_sensitivity_curve() -> None:
    nominal = (4.0, 6.0)
    points = (
        SensitivityPoint(0.05, 0.3, (4.0, 6.0), (4.0, 6.0), (4.0, 6.0), (1.0, 1.0), (0.0, 1.0)),
        SensitivityPoint(0.20, 0.3, (6.5, 6.0), (7.0, 6.5), (7.0, 6.5), (0.2, 1.0), (0.4, 0.6)),
    )

    assert ranking_inversion_cv(nominal, points) == pytest.approx(0.20)
    assert frontier_loss_cv(points) == pytest.approx(0.20)
    assert ranking_inversion_cv((4.0,), points[:1]) is None


def test_normalized_minmax_regret_follows_the_metric_table() -> None:
    ratios = (
        (0.000, 0.276, 0.315),
        (0.006, 0.181, 0.217),
        (0.029, 0.143, 0.177),
        (0.036, 0.137, 0.171),
        (0.062, 0.114, 0.145),
        (0.064, 0.098, 0.131),
        (0.071, 0.064, 0.094),
        (0.103, 0.064, 0.094),
        (0.116, 0.047, 0.077),
        (0.147, 0.047, 0.078),
        (0.153, 0.036, 0.067),
        (0.154, 0.025, 0.053),
        (0.162, 0.020, 0.049),
        (0.177, 0.003, 0.018),
    )
    distance_reference = 1223.6
    time_reference = 17.91
    scored = normalized_minmax_regret(
        [distance_reference * (1 + distance) for distance, _, _ in ratios],
        [time_reference] * len(ratios),
        [time_reference * mean for _, mean, _ in ratios],
        [time_reference * tail for _, _, tail in ratios],
    )

    assert scored[6].score == pytest.approx(0.071)
    assert scored[6].score_p95 == pytest.approx(0.094)
    assert min(range(len(scored)), key=lambda index: scored[index].score) == 6
    assert min(range(len(scored)), key=lambda index: scored[index].score_p95) == 6
    undefined = normalized_minmax_regret([0, 1], [0, 0], [0, 1], [0, 1])
    assert undefined[0].score == 0
    assert undefined[1].score is None


def test_rejects_invalid_routes_and_uncertainty_parameters() -> None:
    time, distance, routes = _dominated_pair()

    with pytest.raises(ValueError, match="exatamente uma vez"):
        analyze_robustness([routes[0][:-2]], distance, time, cv=0, rho=0, rho0=0, scenarios=4, seed=1)
    with pytest.raises(ValueError, match="cv"):
        analyze_robustness(routes, distance, time, cv=-0.1, rho=0, rho0=0, scenarios=4, seed=1)
    with pytest.raises(ValueError, match="rho"):
        analyze_robustness(routes, distance, time, cv=0.2, rho=0.8, rho0=0.3, scenarios=4, seed=1)
    with pytest.raises(ValueError, match="negativos"):
        negative = _blank(4)
        negative[0][1] = -1
        analyze_robustness(routes[:1], distance, negative, cv=0, rho=0, rho0=0, scenarios=4, seed=1)


def test_zero_nominal_arc_stays_zero_under_lognormal_shocks() -> None:
    time, distance, routes = _dominated_pair()
    time[0][1] = 0.0

    report = analyze_robustness(
        routes[:1],
        distance,
        time,
        cv=0.4,
        rho=0,
        rho0=0,
        scenarios=2000,
        seed=7,
        include_sensitivity=False,
    )

    solution = report.solutions[0]
    assert solution.nominal_time == pytest.approx(3)
    assert solution.mean == pytest.approx(3, rel=0.03)
    assert report.deterministic_zero_arcs == 1
    assert solution.critical_arcs
    assert all(arc.nominal_time > 0 for arc in solution.critical_arcs)
    assert sum(arc.variance_share for arc in solution.critical_arcs) == pytest.approx(1)


def test_all_zero_times_remain_deterministic() -> None:
    _, distance, routes = _dominated_pair()

    report = analyze_robustness(
        routes[:1],
        distance,
        _blank(4),
        cv=0.2,
        rho=0,
        rho0=0,
        scenarios=16,
        seed=1,
        include_sensitivity=False,
    )

    solution = report.solutions[0]
    assert solution.nominal_time == 0
    assert solution.mean == 0
    assert solution.stdev == 0
    assert solution.coefficient_of_variation is None
    assert solution.critical_arcs == ()
    assert report.deterministic_zero_arcs == 4
