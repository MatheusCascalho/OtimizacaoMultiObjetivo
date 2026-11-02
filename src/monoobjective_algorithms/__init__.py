"""Shared interfaces for monoobjective optimization algorithms."""

from monoobjective_algorithms.interfaces import (
    MonoobjectiveSolver,
    SolveRequest,
    SolveResult,
    SolverCapabilities,
)

__all__ = [
    "MonoobjectiveSolver",
    "SolveRequest",
    "SolveResult",
    "SolverCapabilities",
]
