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
from multiobjective_algorithms.quality_evolution import (
    IndicatorSample,
    MeanCurve,
    MeanPoint,
    RunIndicatorTrack,
    aggregate_quality_evolution,
    configuration_key,
    is_exact_execution,
    measure_run_indicators,
    sample_iteration_indices,
    select_iteration_moments,
)
from multiobjective_algorithms.spread import (
    RoundSpread,
    SpreadSummary,
    spread_delta,
    summarize_run_spread,
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
    "IndicatorSample",
    "MeanCurve",
    "MeanPoint",
    "ObjectiveSpec",
    "REFERENCE_SHIFT",
    "ReferencePointError",
    "RoundHypervolume",
    "RoundSpread",
    "SpreadSummary",
    "ReferencePoints",
    "ReferenceWarning",
    "RunIndicatorTrack",
    "aggregate_quality_evolution",
    "compute_reference_points",
    "configuration_key",
    "estimate_reference_points",
    "euclidean_distance",
    "hypervolume_2d",
    "is_exact_execution",
    "measure_run_indicators",
    "non_dominated_mask",
    "normalize_objectives",
    "normalized_euclidean_distance",
    "sample_iteration_indices",
    "select_iteration_moments",
    "shift_reference_point",
    "spread_delta",
    "summarize_run_hypervolume",
    "summarize_run_spread",
]
