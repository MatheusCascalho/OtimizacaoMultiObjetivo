"""Repeat the heuristic Pareto sweep without changing each sweep."""

DEFAULT_ITERATIONS = 50
FRONTIER_REPETITIONS = 5
ROUND_SEED_STRIDE = 1_000_003


def total_attempts(iterations: int, repetitions: int = FRONTIER_REPETITIONS) -> int:
    return iterations * repetitions


def round_seed(base_seed: int, round_index: int) -> int:
    """Derive an independent seed for one sweep from the run seed.

    Round 1 keeps the base seed, so that sweep matches a single execution.
    Later rounds shift the seed and stay reproducible from the same base.
    """

    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise ValueError("base_seed must be an integer")
    if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 1:
        raise ValueError("round_index must be an integer starting at 1")
    return (base_seed + (round_index - 1) * ROUND_SEED_STRIDE) & 0x7FFFFFFF
