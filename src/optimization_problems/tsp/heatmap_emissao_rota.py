"""
Gera o PNG de emissão de CO2 de uma rota a partir de CSV.

A conta do fator de velocidade e a densidade suavizada ficam em
``optimization_problems.tsp.emission``. Este script só lê os arquivos e
desenha as duas figuras originais. Distância e tempo são convertidos para km
e horas antes do cálculo.

Uso, a partir da raiz do projeto com ``PYTHONPATH=src``:

  python src/optimization_problems/tsp/heatmap_emissao_rota.py \
      --coords coords.csv --route rota.csv \
      --dist dist.csv --time tempo.csv --dist-unit m --time-unit s \
      --fe-base 0.30 --out heatmap.png
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize

from optimization_problems.tsp.emission import EmissionError, evaluate_route_emission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coords", required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--dist", required=True)
    parser.add_argument("--time", required=True)
    parser.add_argument("--dist-unit", choices=["m", "km"], default="m")
    parser.add_argument("--time-unit", choices=["s", "min", "h"], default="s")
    parser.add_argument("--fe-base", type=float, default=0.30, help="kg CO2/km na faixa eficiente")
    parser.add_argument("--out", default="heatmap.png")
    parser.add_argument("--close-cycle", action="store_true", help="fecha o ciclo voltando ao primeiro nó")
    args = parser.parse_args()

    coords = pd.read_csv(args.coords)
    order = coords["id"].tolist()
    local_id = {node_id: index + 1 for index, node_id in enumerate(order)}
    coordinates = coords[["x", "y"]].to_numpy(float)
    nodes = {
        index + 1: (float(point[0]), float(point[1]))
        for index, point in enumerate(coordinates)
    }

    route_frame = pd.read_csv(args.route, header=0)
    route = route_frame.iloc[:, 0].tolist() if route_frame.shape[1] >= 1 else []
    try:
        route_ids = [local_id[node_id] for node_id in route]
    except KeyError as error:
        raise SystemExit(f"A rota cita um id ausente em coords: {error}") from error

    distance_scale = 1 / 1000 if args.dist_unit == "m" else 1.0
    time_scale = {"s": 1 / 3600, "min": 1 / 60, "h": 1.0}[args.time_unit]
    distance = np.loadtxt(args.dist, delimiter=",") * distance_scale
    time = np.loadtxt(args.time, delimiter=",") * time_scale

    try:
        emission = evaluate_route_emission(
            route_ids,
            distance.tolist(),
            time.tolist(),
            nodes=nodes,
            fe_base_kg_per_km=args.fe_base,
            close_cycle=args.close_cycle,
            include_arcs=True,
            include_heatmap=True,
            resolution=300,
            sigma=6.0,
            padding=20.0,
        )
    except EmissionError as error:
        raise SystemExit(str(error)) from error

    arcs = emission["arcs"]
    print(f"Arcos: {emission['arc_count']} (sem velocidade definida, fator neutro: {emission['unknown_speed_arcs']})")
    print(f"CO2 total (com fator de velocidade): {emission['co2_kg']:.2f} kg")
    print(f"CO2 total (distância x FE base):     {emission['base_co2_kg']:.2f} kg")
    if emission["base_co2_kg"]:
        print(
            f"Excesso por velocidade:              {emission['excess_co2_kg']:.2f} kg "
            f"({100 * (emission['co2_kg'] / emission['base_co2_kg'] - 1):.1f}%)"
        )
    factor = emission["total_speed_emission_factor"]
    if factor is not None:
        print(f"Fator de emissão de velocidade total: {factor:.3f}")

    figure, axes = plt.subplots(1, 2, figsize=(16, 7))
    axis = axes[0]
    if arcs:
        segments = [[nodes[arc["source"]], nodes[arc["target"]]] for arc in arcs]
        factors = np.asarray([arc["speed_factor"] for arc in arcs], dtype=float)
        collection = LineCollection(
            segments,
            cmap="RdYlGn_r",
            norm=Normalize(factors.min(), factors.max()),
            linewidths=2,
        )
        collection.set_array(factors)
        axis.add_collection(collection)
        figure.colorbar(collection, ax=axis, label="Fator relativo (velocidade)")
    axis.scatter(coordinates[:, 0], coordinates[:, 1], s=6, c="k", zorder=3)
    if route_ids:
        depot = nodes[route_ids[0]]
        axis.scatter(*depot, s=60, c="tab:orange", zorder=4, label="Depósito")
        axis.legend()
    axis.autoscale()
    axis.set_aspect("equal")
    axis.invert_yaxis()
    axis.set_title("Fator de emissão por arco")

    axis = axes[1]
    heatmap = emission["heatmap"]
    if heatmap is not None:
        extent = heatmap["extent"]
        image = axis.imshow(
            np.asarray(heatmap["grid"], dtype=float),
            extent=[extent["xmin"], extent["xmax"], extent["ymax"], extent["ymin"]],
            cmap="inferno",
            aspect="equal",
        )
        figure.colorbar(image, ax=axis, label="kg CO2 (relativo)")
    if route_ids:
        ordered = [nodes[node_id] for node_id in route_ids]
        if args.close_cycle and ordered[0] != ordered[-1]:
            ordered.append(ordered[0])
        axis.plot(*zip(*ordered), color="w", lw=0.3, alpha=0.5)
    axis.set_title("Densidade de CO2 (kg, suavizada)")

    plt.tight_layout()
    plt.savefig(args.out, dpi=160)
    print(f"Salvo em {args.out}")


if __name__ == "__main__":
    main()
