---
name: "ParetoLab Algorithm Development"
description: "Use when creating, modifying, reviewing, or testing optimization algorithms, monoobjective solvers, multiobjective analysis, Pareto-front methods, or algorithm notebooks. Follow the project architecture and solver contracts."
applyTo:
  - "**/monoobjective_algorithms/**"
  - "**/multiobjective_algorithms/**"
  - "tests/**/monoobjective_algorithms/**"
  - "tests/**/multiobjective_algorithms/**"
  - "notebooks/**"
---

# Algorithm Development Guidelines

- Before implementing or changing an algorithm, read and follow the canonical specification in [`docs/algorithms/README.md`](../../docs/algorithms/README.md). Treat it as the source of truth; do not copy or redefine its contracts here.
- Keep monoobjective heuristics and exact solvers in `monoobjective_algorithms`, organized by problem family. Make every solver conform to the shared client-facing interface, while declaring and validating any capability differences.
- Keep reusable multiobjective analysis and Pareto-front methods in `multiobjective_algorithms`. Inject solvers through the shared interface; do not couple these methods to a concrete solver, problem representation, API, worker, database, or file-storage adapter.
- Keep reusable algorithm implementations out of notebooks. Notebooks may load instances, configure and call the packages, and present results; place reusable logic in the appropriate package.
- Preserve explicit objective directions and units in comparisons. Handle solver statuses, unsupported capabilities, numerical tolerances, and failures explicitly; never fabricate successful solutions or silently fall back to an incompatible solver.
- Add or update focused tests alongside algorithm changes, covering the shared contract and relevant behavior such as objective direction, dominance, duplicate results, and infeasible or interrupted searches where applicable. Keep tests independent of notebooks and external services.
