from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def build_graph_features(
    costs: Sequence[Sequence[float]],
    candidate_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    matrix = np.asarray(costs, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] < 3:
        raise ValueError("cost matrix must be square with at least three nodes")
    if not np.isfinite(matrix).all():
        raise ValueError("cost matrix must contain only finite numbers")
    if isinstance(candidate_count, bool) or not isinstance(candidate_count, int):
        raise ValueError("candidate_count must be an integer")
    if candidate_count < 1:
        raise ValueError("candidate_count must be positive")

    n_nodes = len(matrix)
    edge_count = min(candidate_count, n_nodes - 1)
    scale = float(np.mean(np.abs(matrix[matrix != 0])))
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    normalized = matrix / scale

    node_features = np.stack(
        (
            normalized.mean(axis=1),
            normalized.std(axis=1),
            normalized.mean(axis=0),
            normalized.std(axis=0),
        ),
        axis=-1,
    ).astype(np.float32)
    edge_index = np.empty((n_nodes, edge_count), dtype=np.int64)
    edge_features = np.empty((n_nodes, edge_count), dtype=np.float32)
    edge_positions: dict[tuple[int, int], int] = {}
    for source in range(n_nodes):
        neighbors = sorted(
            (target for target in range(n_nodes) if target != source),
            key=lambda target: (normalized[source, target], target),
        )[:edge_count]
        edge_index[source] = neighbors
        for position, target in enumerate(neighbors):
            edge_positions[source, target] = source * edge_count + position
            edge_features[source, position] = normalized[source, target]

    sentinel = n_nodes * edge_count
    inverse_edge_index = np.full(sentinel, sentinel, dtype=np.int64)
    for (source, target), position in edge_positions.items():
        inverse_edge_index[position] = edge_positions.get(
            (target, source), sentinel
        )

    return (
        node_features[None, :, :],
        edge_features.reshape(1, -1, 1),
        edge_index[None, :, :],
        inverse_edge_index[None, :],
        scale,
    )


def candidate_file_contents(candidates: Sequence[Sequence[int]]) -> str:
    n_nodes = len(candidates)
    lines = [str(n_nodes)]
    for source, neighbors in enumerate(candidates, start=1):
        unique_neighbors = tuple(dict.fromkeys(neighbors))
        if source - 1 in unique_neighbors:
            raise ValueError("candidate set cannot contain self loops")
        if any(target < 0 or target >= n_nodes for target in unique_neighbors):
            raise ValueError("candidate node index is outside the graph")
        fields = [str(source), "0", str(len(unique_neighbors))]
        for rank, target in enumerate(unique_neighbors):
            fields.extend((str(target + 1), str(rank * 100)))
        lines.append(" ".join(fields))
    lines.extend(("-1", "EOF"))
    return "\n".join(lines) + "\n"


def transform_atsp_guidance(
    candidates: Sequence[Sequence[int]],
    penalties: Sequence[float],
    candidate_limit: int,
) -> tuple[tuple[tuple[int, ...], ...], tuple[float, ...]]:
    n_nodes = len(candidates)
    if n_nodes < 3 or len(penalties) != n_nodes:
        raise ValueError("ATSP guidance must contain matching nodes and penalties")
    if isinstance(candidate_limit, bool) or not isinstance(candidate_limit, int):
        raise ValueError("candidate_limit must be an integer")
    if candidate_limit < 1:
        raise ValueError("candidate_limit must be positive")

    transformed: list[list[int]] = [[] for _ in range(2 * n_nodes)]
    for source, neighbors in enumerate(candidates):
        for target in neighbors:
            if isinstance(target, bool) or not isinstance(target, int):
                raise ValueError("candidate node indices must be integers")
            if target < 0 or target >= n_nodes or target == source:
                raise ValueError("candidate node index is invalid for ATSP")
            transformed[source].append(target + n_nodes)
            transformed[n_nodes + target].append(source)

    transformed_candidates = tuple(
        tuple(dict.fromkeys(neighbors))[:candidate_limit]
        for neighbors in transformed
    )
    transformed_penalties = tuple(float(value) for value in penalties) * 2
    return transformed_candidates, transformed_penalties


def penalty_file_contents(penalties: Sequence[float], scale: float) -> str:
    values = np.asarray(penalties, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("node penalties must be a finite vector")
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("penalty scale must be finite and positive")

    lines = [str(len(values))]
    lines.extend(
        f"{node} {int(round(penalty * scale))}"
        for node, penalty in enumerate(values, start=1)
    )
    return "\n".join(lines) + "\n"
