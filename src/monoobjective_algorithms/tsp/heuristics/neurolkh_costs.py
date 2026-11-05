"""Integer LKH weights and classical MDS coordinates for a symmetric cost matrix.

The Jonker-Volgenant matrix is not a Euclidean distance: the diagonal carries
the penalty, coupling edges are ``-penalty``, and forbidden edges are
``penalty``. Coordinates below are derived only as input for the pretrained
network. The integer matrix is what LKH optimizes.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

# CreateCandidateSet multiplies every explicit cost by LKH's Precision (100).
# The product has to stay inside a signed 32-bit int, so each weight is capped
# at 20_000_000 before that multiplication.
INTEGER_COST_BUDGET = 20_000_000


def scale_symmetric_costs(
    matrix: np.ndarray,
) -> tuple[np.ndarray, Mapping[str, float]]:
    """Map a symmetric float matrix onto positive integers for LKH.

    ``shift`` is the minimum off-diagonal cost, which on a Jonker-Volgenant
    matrix is the coupling weight ``-penalty``. The scale is the largest value
    that keeps every shifted entry inside ``INTEGER_COST_BUDGET - 2``:

        w_ij = round(scale * (c_ij - shift))

    A final uniform increment makes every off-diagonal weight at least 1.
    If rounding would make a coupling edge at least as expensive as a real
    transition, those transitions (and the forbidden edges) are increased so
    coupling stays strictly cheaper. Gaps smaller than about ``1 / scale``
    can collapse; the penalty term dominates the span, so ``scale`` shrinks
    as the instance grows.
    """

    costs = np.asarray(matrix, dtype=float)
    if costs.ndim != 2 or costs.shape[0] != costs.shape[1] or costs.shape[0] < 2:
        raise ValueError("cost matrix must be square and have at least two nodes")
    if not np.all(np.isfinite(costs)):
        raise ValueError("cost matrix must be finite")

    costs = 0.5 * (costs + costs.T)
    size = costs.shape[0]
    off = ~np.eye(size, dtype=bool)
    shift = float(np.min(costs[off]))
    shifted = costs - shift
    span = float(np.max(shifted[off]))
    scale = 1.0 if span == 0 else (INTEGER_COST_BUDGET - 2) / span

    scaled = np.rint(scale * shifted).astype(np.int64)
    np.fill_diagonal(scaled, 0)

    minimum = float(np.min(costs[off]))
    maximum = float(np.max(costs[off]))
    coupling = off & (costs == minimum)
    forbidden = off & (costs == maximum) & ~coupling
    real = off & ~coupling & ~forbidden
    if np.any(coupling) and np.any(real):
        gap = int(scaled[coupling].max() - scaled[real].min() + 1)
        if gap > 0:
            scaled[real] += gap
            if np.any(forbidden):
                scaled[forbidden] += gap

    lowest = int(scaled[off].min())
    if lowest < 1:
        scaled[off] += 1 - lowest
    np.fill_diagonal(scaled, 0)

    if int(scaled[off].max()) > INTEGER_COST_BUDGET:
        raise ValueError("integer edge weights do not fit in the LKH budget")
    if np.any(coupling) and np.any(real) and int(scaled[coupling].max()) >= int(scaled[real].min()):
        raise ValueError("coupling edges are not strictly cheaper than real transitions")

    return scaled, {"scale": float(scale), "shift": shift, "budget": float(INTEGER_COST_BUDGET)}


def coordinates_from_symmetric_costs(matrix: np.ndarray) -> np.ndarray:
    """Classical MDS coordinates in ``[0, 1]``, for the network only.

    The raw symmetric matrix is shifted so its cheapest off-diagonal entry is
    zero and the diagonal is cleared. That produces a non-negative dissimilarity
    for Torgerson MDS. The embedding is not the objective LKH optimizes.
    """

    costs = np.asarray(matrix, dtype=float)
    size = costs.shape[0]
    off = ~np.eye(size, dtype=bool)
    distance = costs - float(np.min(costs[off]))
    np.fill_diagonal(distance, 0.0)
    distance = np.maximum(0.5 * (distance + distance.T), 0.0)

    centering = np.eye(size) - np.ones((size, size)) / size
    gram = -0.5 * centering @ (distance ** 2) @ centering
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1][:2]
    values = np.clip(eigenvalues[order], 0.0, None)
    coords = eigenvectors[:, order] * np.sqrt(values)
    if coords.shape[1] < 2:
        coords = np.pad(coords, ((0, 0), (0, 2 - coords.shape[1])))
    for axis in range(coords.shape[1]):
        pivot = int(np.argmax(np.abs(coords[:, axis])))
        if coords[pivot, axis] < 0:
            coords[:, axis] *= -1.0
    return _unit_square(coords)


def _unit_square(coords: np.ndarray) -> np.ndarray:
    low = coords.min(axis=0)
    span = coords.max(axis=0) - low
    normalized = np.empty_like(coords, dtype=float)
    for axis, width in enumerate(span):
        if width == 0:
            normalized[:, axis] = 0.5
        else:
            normalized[:, axis] = (coords[:, axis] - low[axis]) / width
    return normalized
