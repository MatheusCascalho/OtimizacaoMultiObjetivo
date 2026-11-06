"""Reusable multiobjective analysis tools."""

from multiobjective_algorithms.dominance import non_dominated_mask
from multiobjective_algorithms.hypervolume import (
    HypervolumeSummary,
    REFERENCE_SHIFT,
    RoundHypervolume,
    hypervolume_2d,
    shift_reference_point,
    summarize_run_hypervolume,
)
from multiobjective_algorithms.reference_points import (
    ObjectiveSpec,
    ReferencePointError,
    ReferencePoints,
    ReferenceWarning,
    compute_reference_points,
    estimate_reference_points,
    euclidean_distance,
    normalize_objectives,
    normalized_euclidean_distance,
)

__all__ = [
    "HypervolumeSummary",
    "ObjectiveSpec",
    "REFERENCE_SHIFT",
    "ReferencePointError",
    "RoundHypervolume",
    "ReferencePoints",
    "ReferenceWarning",
    "compute_reference_points",
    "estimate_reference_points",
    "euclidean_distance",
    "hypervolume_2d",
    "non_dominated_mask",
    "normalize_objectives",
    "normalized_euclidean_distance",
    "shift_reference_point",
    "summarize_run_hypervolume",
]
