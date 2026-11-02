from __future__ import annotations

from math import isfinite
from typing import Literal, Mapping

from pyomo.environ import (
    Binary,
    ConcreteModel,
    Constraint,
    Expression,
    NonNegativeReals,
    Objective,
    Param,
    RangeSet,
    Set,
    Var,
    minimize,
)

from optimization_problems.tsp.instance import TSPInstance

TSPObjective = Literal["time", "distance"]
_OBJECTIVES = frozenset({"time", "distance"})


class TSPBiobjectiveModelBuilder:
    """Build the directed biobjective TSP MILP with an active scalar objective.

    Both objective expressions are retained on the model. One is minimized,
    while limits may be applied to the other for epsilon-constraint runs.
    Node 1 is the depot, matching the MTZ formulation in the project reference.
    """

    def build(
        self,
        instance: TSPInstance,
        objective: TSPObjective = "time",
        objective_limits: Mapping[str, float] | None = None,
    ) -> ConcreteModel:
        if not isinstance(objective, str) or objective not in _OBJECTIVES:
            raise ValueError("objective must be 'time' or 'distance'")

        limits = self._validate_limits(objective, objective_limits or {})
        node_count = instance.node_count
        nodes = range(1, node_count + 1)
        non_depot_nodes = range(2, node_count + 1)
        arcs = tuple((i, j) for i in nodes for j in nodes if i != j)
        mtz_arcs = tuple(
            (i, j)
            for i in non_depot_nodes
            for j in non_depot_nodes
            if i != j
        )

        model = ConcreteModel(name="TSPBiobjective")
        model.nodes = RangeSet(1, node_count)
        model.non_depot_nodes = RangeSet(2, node_count)
        model.arcs = Set(dimen=2, initialize=arcs)
        model.mtz_arcs = Set(dimen=2, initialize=mtz_arcs)
        model.x = Var(model.arcs, domain=Binary)
        model.u = Var(
            model.non_depot_nodes,
            domain=NonNegativeReals,
            bounds=(1, node_count - 1),
        )

        model.time_cost = Param(
            model.arcs,
            initialize={
                (i, j): instance.time_matrix[i - 1][j - 1]
                for i, j in arcs
            },
        )
        model.distance_cost = Param(
            model.arcs,
            initialize={
                (i, j): instance.distance_matrix[i - 1][j - 1]
                for i, j in arcs
            },
        )

        model.out_degree = Constraint(
            model.nodes,
            rule=lambda m, i: sum(m.x[i, j] for j in m.nodes if i != j) == 1,
        )
        model.in_degree = Constraint(
            model.nodes,
            rule=lambda m, j: sum(m.x[i, j] for i in m.nodes if i != j) == 1,
        )
        model.mtz = Constraint(
            model.mtz_arcs,
            rule=lambda m, i, j: m.u[i] - m.u[j] + (node_count - 1) * m.x[i, j]
            <= node_count - 2,
        )

        model.total_time = Expression(
            expr=sum(model.time_cost[i, j] * model.x[i, j] for i, j in arcs)
        )
        model.total_distance = Expression(
            expr=sum(model.distance_cost[i, j] * model.x[i, j] for i, j in arcs)
        )
        model.objective = Objective(
            expr=getattr(model, f"total_{objective}"),
            sense=minimize,
        )

        for metric, limit in limits.items():
            setattr(
                model,
                f"{metric}_limit",
                Constraint(expr=getattr(model, f"total_{metric}") <= limit),
            )

        return model

    @staticmethod
    def _validate_limits(
        objective: TSPObjective,
        objective_limits: Mapping[str, float],
    ) -> dict[str, float]:
        limits: dict[str, float] = {}
        for metric, raw_limit in objective_limits.items():
            if metric not in _OBJECTIVES:
                raise ValueError(f"unsupported objective limit: {metric}")
            if metric == objective:
                raise ValueError("objective_limits may only constrain non-primary objectives")
            if isinstance(raw_limit, (bool, str, bytes)):
                raise ValueError(f"{metric} limit must be a finite number")
            try:
                limit = float(raw_limit)
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(f"{metric} limit must be a finite number") from error
            if not isfinite(limit):
                raise ValueError(f"{metric} limit must be a finite number")
            limits[metric] = limit
        return limits
