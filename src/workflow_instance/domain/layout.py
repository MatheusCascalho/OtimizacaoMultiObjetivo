from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def prepare_distance_matrix(matrix: Sequence[Sequence[float]]) -> np.ndarray:
    """Converte a matriz da instância em uma matriz válida para MDS clássico."""
    D = np.asarray(matrix, dtype=float)
    if D.ndim != 2 or D.shape[0] != D.shape[1]:
        raise ValueError("A matriz deve ser quadrada.")
    if not np.all(np.isfinite(D)):
        raise ValueError("A matriz contém valores não finitos.")

    # Valores negativos significam "sem aresta": substitui pelo maior valor válido
    valid = D[D >= 0]
    if valid.size == 0:
        raise ValueError("A matriz não possui valores válidos.")
    D = np.where(D < 0, valid.max(), D)

    D = (D + D.T) / 2.0          # simetriza (tempos podem ser assimétricos)
    np.fill_diagonal(D, 0.0)
    return D


def torgerson_coordinates(dist: np.ndarray, n_components: int = 2) -> np.ndarray:
    """MDS clássico (Torgerson, 1952). Retorna array (n, n_components)."""
    n = dist.shape[0]
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ (dist ** 2) @ J

    eigvals, eigvecs = np.linalg.eigh(B)
    idx = np.argsort(eigvals)[::-1][:n_components]
    vals = np.clip(eigvals[idx], 0, None)
    coords = eigvecs[:, idx] * np.sqrt(vals)

    if coords.shape[1] < n_components:  # n < n_components
        pad = np.zeros((n, n_components - coords.shape[1]))
        coords = np.hstack([coords, pad])

    # Torna o sinal de cada eixo determinístico (autovetores têm sinal arbitrário)
    for k in range(n_components):
        if coords[np.argmax(np.abs(coords[:, k])), k] < 0:
            coords[:, k] *= -1
    return coords


def fit_to_box(coords: np.ndarray, size: float = 200.0) -> np.ndarray:
    """Centraliza em (size/2, size/2) e reescala mantendo a proporção."""
    centered = coords - coords.mean(axis=0)
    extent = np.abs(centered).max()
    if extent == 0:
        return np.full_like(centered, size / 2)
    return centered / extent * (size / 2) + size / 2


def mds_layout(matrix: Sequence[Sequence[float]], size: float = 200.0) -> np.ndarray:
    D = prepare_distance_matrix(matrix)
    return fit_to_box(torgerson_coordinates(D, 2), size)