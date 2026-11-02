from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Literal, Mapping, Protocol, TypeVar

InstanceT = TypeVar("InstanceT", contravariant=True)
SolutionT = TypeVar("SolutionT", covariant=True)

SolveStatus = Literal["optimal", "feasible", "infeasible", "limit_reached", "failed"]


@dataclass(frozen=True)
class SolverCapabilities:
    supports_objective_limits: bool = False


@dataclass(frozen=True)
class SolveRequest:
    objective: str
    objective_limits: Mapping[str, float] = field(default_factory=dict)
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SolveResult(Generic[SolutionT]):
    status: SolveStatus
    solution: SolutionT | None
    objective_values: Mapping[str, float]


class MonoobjectiveSolver(Protocol[InstanceT, SolutionT]):
    @property
    def algorithm_id(self) -> str: ...

    @property
    def capabilities(self) -> SolverCapabilities: ...

    def solve(
        self,
        instance: InstanceT,
        request: SolveRequest,
    ) -> SolveResult[SolutionT]: ...
