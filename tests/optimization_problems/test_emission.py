import numpy as np
import pytest

from optimization_problems.tsp.emission import (
    EmissionError,
    evaluate_route_emission,
    speed_factor,
)


DISTANCE = (
    (0.0, 10.0, 10.0),
    (10.0, 0.0, 10.0),
    (10.0, 10.0, 0.0),
)
TIME = (
    (0.0, 1.0, 0.1),
    (0.5, 0.0, 0.2),
    (0.1, 1.0, 0.0),
)
NODES = {1: (0.0, 0.0), 2: (10.0, 0.0), 3: (10.0, 10.0)}


def test_speed_bands_use_the_lower_bound_of_each_interval() -> None:
    assert speed_factor(0) == 1.5
    assert speed_factor(19.9) == 1.5
    assert speed_factor(20) == 1.15
    assert speed_factor(40) == 1.0
    assert speed_factor(70) == 1.2
    assert speed_factor(130) == 1.2


def test_total_factor_is_the_distance_weighted_mean() -> None:
    emission = evaluate_route_emission([1, 2, 3, 1], DISTANCE, TIME)

    assert emission["co2_kg"] == pytest.approx(4.5 + 3.0 + 3.6)
    assert emission["base_co2_kg"] == pytest.approx(9.0)
    assert emission["total_speed_emission_factor"] == pytest.approx(11.1 / 9.0)
    assert emission["unknown_speed_arcs"] == 0
    assert emission["heatmap"] is None


def test_reversed_route_uses_the_asymmetric_time() -> None:
    emission = evaluate_route_emission([1, 3, 2, 1], DISTANCE, TIME)

    assert emission["co2_kg"] == pytest.approx(3.6 + 4.5 + 3.45)
    assert emission["total_speed_emission_factor"] == pytest.approx(11.55 / 9.0)


def test_open_route_is_closed_before_the_return_arc() -> None:
    emission = evaluate_route_emission(
        [1, 2],
        ((0.0, 10.0), (4.0, 0.0)),
        ((0.0, 1.0), (0.5, 0.0)),
        include_arcs=True,
    )

    assert [(arc["source"], arc["target"]) for arc in emission["arcs"]] == [(1, 2), (2, 1)]
    assert emission["arcs"][1]["speed_kmh"] == pytest.approx(8.0)
    assert emission["arcs"][1]["speed_factor"] == 1.5


def test_zero_time_keeps_a_neutral_factor() -> None:
    emission = evaluate_route_emission(
        [1, 2, 1],
        ((0.0, 10.0), (10.0, 0.0)),
        ((0.0, 0.0), (0.0, 0.0)),
        include_arcs=True,
    )

    assert emission["unknown_speed_arcs"] == 2
    assert emission["arcs"][0]["speed_kmh"] is None
    assert emission["total_speed_emission_factor"] == pytest.approx(1.0)
    assert emission["co2_kg"] == pytest.approx(6.0)


def test_unsmoothed_density_preserves_the_co2_mass() -> None:
    emission = evaluate_route_emission(
        [1, 2, 1],
        ((0.0, 10.0), (10.0, 0.0)),
        ((0.0, 0.5), (0.5, 0.0)),
        nodes=NODES,
        include_heatmap=True,
        resolution=40,
        sigma=0,
        padding=5,
    )

    grid = emission["heatmap"]["grid"]
    assert emission["heatmap"]["row_origin"] == "ymin"
    assert len(grid) == 40
    assert len(grid[0]) == 40
    assert sum(sum(row) for row in grid) == pytest.approx(emission["co2_kg"], rel=1e-4)
    assert emission["heatmap"]["extent"]["xmin"] < 0
    assert emission["heatmap"]["extent"]["xmax"] > 10


def test_gaussian_smooth_matches_scipy() -> None:
    scipy_ndimage = pytest.importorskip("scipy.ndimage")
    from optimization_problems.tsp.emission import _gaussian_smooth

    grid = np.arange(48, dtype=float).reshape(6, 8)
    smoothed = _gaussian_smooth(grid, 1.25)
    reference = scipy_ndimage.gaussian_filter(grid, 1.25)

    assert smoothed.shape == grid.shape
    assert np.allclose(smoothed, reference, atol=1e-10)


def test_missing_layout_reports_why_the_heatmap_is_absent() -> None:
    emission = evaluate_route_emission(
        [1, 2, 1],
        ((0.0, 10.0), (10.0, 0.0)),
        ((0.0, 1.0), (1.0, 0.0)),
        include_heatmap=True,
    )

    assert emission["heatmap"] is None
    assert emission["total_speed_emission_factor"] == pytest.approx(1.5)
    assert "layout" in emission["heatmap_message"]


def test_city_outside_the_matrix_is_rejected() -> None:
    with pytest.raises(EmissionError):
        evaluate_route_emission([1, 4, 1], DISTANCE, TIME)


def test_fe_base_must_be_positive() -> None:
    with pytest.raises(EmissionError):
        evaluate_route_emission([1, 2, 1], DISTANCE, TIME, fe_base_kg_per_km=0)
