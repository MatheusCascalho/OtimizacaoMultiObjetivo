import pytest

from workflow_instance.domain.frontier_sampling import (
    DEFAULT_ITERATIONS,
    FRONTIER_REPETITIONS,
    round_seed,
    total_attempts,
)


def test_frontier_mapping_repeats_five_rounds_of_fifty_attempts() -> None:
    assert FRONTIER_REPETITIONS == 5
    assert DEFAULT_ITERATIONS == 50
    assert total_attempts(DEFAULT_ITERATIONS) == 250
    assert total_attempts(50, FRONTIER_REPETITIONS) == 5 * 50


def test_each_round_keeps_an_independent_reproducible_seed() -> None:
    assert round_seed(7, 1) == 7
    seeds = [round_seed(7, round_index) for round_index in range(1, 6)]
    assert len(set(seeds)) == 5

    with pytest.raises(ValueError):
        round_seed(7, 0)
