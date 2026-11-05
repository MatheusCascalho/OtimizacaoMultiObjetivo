"""KPIs do tempo de parede de cada tentativa concluída.

Cada chamada da heurística que devolve uma solução entra na amostra,
em todas as rodadas. Rotas repetidas, deduplicadas depois na fronteira,
continuam contando. A máscara de não dominância não filtra estes tempos.
"""

from __future__ import annotations

from math import isfinite
from statistics import fmean, stdev
from typing import Mapping, Sequence


def solution_timing_kpis(samples: Sequence[Mapping[str, object]] | None) -> dict | None:
    """Return mean, sample standard deviation, and the extreme attempts.

    Samples are ordered by round, then attempt. Ties keep the first sample
    in that order. A single sample has standard deviation 0. An empty
    sample has no KPIs.
    """

    ordered = _ordered_samples(samples or [])
    if not ordered:
        return None
    durations = [sample["duration_ms"] for sample in ordered]
    count = len(durations)
    return {
        "unit": "ms",
        "count": count,
        "mean_ms": fmean(durations),
        "sample_stdev_ms": 0.0 if count == 1 else stdev(durations),
        "slowest": _extreme(ordered, choose_slower=True),
        "fastest": _extreme(ordered, choose_slower=False),
    }


def _ordered_samples(samples: Sequence[Mapping[str, object]]) -> list[dict]:
    normalized = [_normalize_sample(sample) for sample in samples]
    return sorted(normalized, key=lambda sample: (sample["round"], sample["attempt"]))


def _normalize_sample(sample: Mapping[str, object]) -> dict:
    round_index = sample.get("round")
    attempt = sample.get("attempt")
    duration_ms = sample.get("duration_ms")
    if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 1:
        raise ValueError("round must be an integer starting at 1")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt must be an integer starting at 1")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)):
        raise ValueError("duration_ms must be a non-negative finite number")
    duration = float(duration_ms)
    if not isfinite(duration) or duration < 0:
        raise ValueError("duration_ms must be a non-negative finite number")
    return {"round": round_index, "attempt": attempt, "duration_ms": duration}


def _extreme(ordered: Sequence[dict], choose_slower: bool) -> dict:
    selected = ordered[0]
    for sample in ordered[1:]:
        is_more_extreme = (
            sample["duration_ms"] > selected["duration_ms"]
            if choose_slower
            else sample["duration_ms"] < selected["duration_ms"]
        )
        if is_more_extreme:
            selected = sample
    return dict(selected)
