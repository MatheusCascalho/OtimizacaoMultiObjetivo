"""Emissão de CO2 de uma rota TSP com fator dependente da velocidade.

A distância entra em quilômetros e o tempo em horas, que são as unidades das
matrizes do TSP biobjetivo. O CO2 de cada arco é

    distância_km × fe_base × fator(velocidade)

com ``fe_base`` em kg/km. O fator total da solução é a média desses fatores
ponderada pela distância, equivalente a CO2 com velocidade dividido pelo CO2
que usaria só o fator base.
"""

from __future__ import annotations

from math import isfinite
from numbers import Integral, Real
from typing import Mapping, Sequence

import numpy as np


SPEED_BANDS_KMH: tuple[tuple[float, float, float], ...] = (
    (0.0, 20.0, 1.5),
    (20.0, 40.0, 1.15),
    (40.0, 70.0, 1.0),
    (70.0, float("inf"), 1.2),
)
DEFAULT_FE_BASE_KG_PER_KM = 0.30
DEFAULT_HEATMAP_RESOLUTION = 160


class EmissionError(ValueError):
    """A rota ou o fator base não permitem calcular a emissão."""


def speed_factor(speed_kmh: float) -> float:
    """Fator relativo da faixa de velocidade. Acima de 70 km/h permanece 1,2."""

    for low, high, factor in SPEED_BANDS_KMH:
        if low <= speed_kmh < high:
            return factor
    return 1.0


def speed_bands_payload() -> list[dict[str, float | None]]:
    return [
        {
            "min_speed_kmh": low,
            "max_speed_kmh": None if high == float("inf") else high,
            "factor": factor,
        }
        for low, high, factor in SPEED_BANDS_KMH
    ]


def evaluate_route_emission(
    route: Sequence[object],
    distance_matrix: Sequence[Sequence[float]],
    time_matrix: Sequence[Sequence[float]],
    *,
    nodes: Mapping[int, tuple[float, float]] | None = None,
    fe_base_kg_per_km: float = DEFAULT_FE_BASE_KG_PER_KM,
    close_cycle: bool = True,
    include_arcs: bool = False,
    include_heatmap: bool = False,
    resolution: int = DEFAULT_HEATMAP_RESOLUTION,
    sigma: float | None = None,
    padding: float | None = None,
) -> dict[str, object]:
    """Calcula o fator total e, quando pedido, a densidade suavizada de CO2."""

    fe_base = _fe_base(fe_base_kg_per_km)
    cities = _closed_route(route, close_cycle)
    arcs = _arcs(cities, distance_matrix, time_matrix, fe_base)
    distance_km = sum(arc["distance_km"] for arc in arcs)
    co2_kg = sum(arc["co2_kg"] for arc in arcs)
    base_co2_kg = distance_km * fe_base
    heatmap = None
    heatmap_message = None
    if include_heatmap:
        heatmap, heatmap_message = _heatmap(
            arcs,
            nodes or {},
            resolution=resolution,
            sigma=sigma,
            padding=padding,
        )
    payload: dict[str, object] = {
        "fe_base_kg_per_km": fe_base,
        "distance_unit": "km",
        "time_unit": "h",
        "co2_unit": "kg",
        "bands": speed_bands_payload(),
        "arc_count": len(arcs),
        "unknown_speed_arcs": sum(arc["speed_kmh"] is None for arc in arcs),
        "distance_km": distance_km,
        "base_co2_kg": base_co2_kg,
        "co2_kg": co2_kg,
        "excess_co2_kg": co2_kg - base_co2_kg,
        "total_speed_emission_factor": (co2_kg / base_co2_kg) if base_co2_kg > 0 else None,
        "heatmap": heatmap,
        "heatmap_message": heatmap_message,
    }
    if include_arcs:
        payload["arcs"] = arcs
    return payload


def _fe_base(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise EmissionError("O fator base de emissão deve ser um número positivo.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise EmissionError("O fator base de emissão deve ser um número positivo.") from error
    if not isfinite(number) or number <= 0:
        raise EmissionError("O fator base de emissão deve ser um número positivo.")
    return number


def _city_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise EmissionError("A rota contém uma cidade que não é um identificador inteiro.")
    city = int(value)
    if city < 1:
        raise EmissionError("A rota contém uma cidade fora da matriz.")
    return city


def _closed_route(route: Sequence[object], close_cycle: bool) -> list[int]:
    if isinstance(route, (str, bytes)) or not isinstance(route, Sequence):
        raise EmissionError("A rota deve ser uma sequência de cidades.")
    cities = [_city_id(city) for city in route]
    if close_cycle and cities and cities[0] != cities[-1]:
        cities.append(cities[0])
    return cities


def _cell(matrix: Sequence[Sequence[float]], source: int, target: int) -> float:
    row_index = source - 1
    column_index = target - 1
    if row_index >= len(matrix):
        raise EmissionError(f"A rota usa a cidade {source}, fora da matriz.")
    row = matrix[row_index]
    if column_index >= len(row):
        raise EmissionError(f"A rota usa a cidade {target}, fora da matriz.")
    value = row[column_index]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise EmissionError("A matriz contém um valor que não é numérico.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise EmissionError("A matriz contém um valor que não é numérico.") from error
    if not isfinite(number):
        raise EmissionError("A matriz contém um valor não finito.")
    return number


def _arcs(
    cities: Sequence[int],
    distance_matrix: Sequence[Sequence[float]],
    time_matrix: Sequence[Sequence[float]],
    fe_base: float,
) -> list[dict[str, float | int | None]]:
    arcs: list[dict[str, float | int | None]] = []
    for source, target in zip(cities, cities[1:]):
        distance_km = _cell(distance_matrix, source, target)
        time_h = _cell(time_matrix, source, target)
        if distance_km <= 0:
            continue
        if time_h <= 0:
            speed_kmh: float | None = None
            factor = 1.0
        else:
            speed_kmh = distance_km / time_h
            factor = speed_factor(speed_kmh)
        arcs.append(
            {
                "source": source,
                "target": target,
                "distance_km": distance_km,
                "time_h": time_h,
                "speed_kmh": speed_kmh,
                "speed_factor": factor,
                "co2_kg": distance_km * fe_base * factor,
            }
        )
    return arcs


def _node_xy(nodes: Mapping[int, tuple[float, float]], city: int) -> tuple[float, float] | None:
    point = nodes.get(city)
    if point is None or len(point) != 2:
        return None
    try:
        x = float(point[0])
        y = float(point[1])
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(x) or not isfinite(y):
        return None
    return x, y


def _heatmap(
    arcs: Sequence[dict[str, float | int | None]],
    nodes: Mapping[int, tuple[float, float]],
    *,
    resolution: int,
    sigma: float | None,
    padding: float | None,
) -> tuple[dict[str, object] | None, str | None]:
    if isinstance(resolution, bool) or not isinstance(resolution, Integral):
        raise EmissionError("A resolução do heatmap deve ser um inteiro positivo.")
    size = int(resolution)
    if size < 8 or size > 400:
        raise EmissionError("A resolução do heatmap deve ficar entre 8 e 400.")
    coordinates = [_node_xy(nodes, city) for city in nodes]
    if not coordinates or any(point is None for point in coordinates):
        return None, "O layout das cidades não está disponível para desenhar a densidade de CO2."
    placed = [point for point in coordinates if point is not None]
    for arc in arcs:
        if _node_xy(nodes, int(arc["source"])) is None or _node_xy(nodes, int(arc["target"])) is None:
            return None, "A densidade de CO2 exige as coordenadas de todas as cidades da rota."

    points = np.asarray(placed, dtype=float)
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    span = max(float(maximum[0] - minimum[0]), float(maximum[1] - minimum[1]), 1e-9)
    if padding is None:
        pad = 0.08 * span
    else:
        if isinstance(padding, bool) or not isinstance(padding, Real):
            raise EmissionError("A margem do heatmap deve ser um número não negativo.")
        pad = float(padding)
        if not isfinite(pad) or pad < 0:
            raise EmissionError("A margem do heatmap deve ser um número não negativo.")
    xmin, ymin = minimum - pad
    xmax, ymax = maximum + pad
    if xmax <= xmin:
        xmax = xmin + 1.0
    if ymax <= ymin:
        ymax = ymin + 1.0

    blur = (6.0 * size / 300.0) if sigma is None else float(sigma)
    if not isfinite(blur) or blur < 0:
        raise EmissionError("O desvio da suavização deve ser um número não negativo.")

    grid = np.zeros((size, size), dtype=float)
    width = xmax - xmin
    height = ymax - ymin
    for arc in arcs:
        start = _node_xy(nodes, int(arc["source"]))
        end = _node_xy(nodes, int(arc["target"]))
        if start is None or end is None:
            continue
        origin = np.asarray(start, dtype=float)
        destination = np.asarray(end, dtype=float)
        samples = max(int(np.hypot(*(destination - origin)) / (width / size)) + 2, 2)
        step = np.linspace(0.0, 1.0, samples)
        px = origin[0] + step * (destination[0] - origin[0])
        py = origin[1] + step * (destination[1] - origin[1])
        gx = np.clip(((px - xmin) / width * (size - 1)).astype(int), 0, size - 1)
        gy = np.clip(((py - ymin) / height * (size - 1)).astype(int), 0, size - 1)
        emission = float(arc["co2_kg"])
        np.add.at(grid, (gy, gx), emission / samples)
    grid = _gaussian_smooth(grid, blur)
    return (
        {
            "title": "Densidade de CO2 (kg, suavizada)",
            "unit": "kg",
            "smoothing": "gaussian",
            "sigma": float(blur),
            "resolution": size,
            "row_origin": "ymin",
            "extent": {
                "xmin": float(xmin),
                "xmax": float(xmax),
                "ymin": float(ymin),
                "ymax": float(ymax),
            },
            "grid": _grid_lists(grid),
        },
        None,
    )


def _gaussian_smooth(grid: np.ndarray, sigma: float) -> np.ndarray:
    """Suavização gaussiana separável, no modo reflect do SciPy."""

    values = np.asarray(grid, dtype=float)
    if sigma <= 0:
        return values.copy()
    radius = int(4.0 * float(sigma) + 0.5)
    if radius < 1:
        return values.copy()
    offsets = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (offsets / float(sigma)) ** 2)
    kernel /= kernel.sum()

    def along(array: np.ndarray, axis: int) -> np.ndarray:
        def convolve(line: np.ndarray) -> np.ndarray:
            width = min(radius, max(int(line.size) - 1, 0))
            if width <= 0:
                return line.astype(float, copy=True)
            used = kernel
            if width != radius:
                used = kernel[radius - width : radius + width + 1]
                used = used / used.sum()
            padded = np.pad(line, width, mode="symmetric")
            return np.convolve(padded, used, mode="valid")

        return np.apply_along_axis(convolve, axis, array)

    return along(along(values, 0), 1)


def _grid_lists(grid: np.ndarray) -> list[list[float]]:
    rounded = np.round(grid, 6)
    return [[float(f"{value:.6f}") for value in row] for row in rounded]
