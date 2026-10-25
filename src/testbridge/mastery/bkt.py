"""Per-concept Bayesian Knowledge Tracing with fixed defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.3
    p_learn: float = 0.15
    p_guess: float = 0.2
    p_slip: float = 0.1


@dataclass(frozen=True)
class BKTState:
    p: float
    observations: int


def initial_state(params: BKTParams | None = None) -> BKTState:
    params = params or BKTParams()
    return BKTState(p=params.p_init, observations=0)


def observe(state: BKTState, correct: bool, params: BKTParams | None = None) -> BKTState:
    params = params or BKTParams()
    p = state.p
    if correct:
        p_obs = p * (1 - params.p_slip) / (
            p * (1 - params.p_slip) + (1 - p) * params.p_guess
        )
    else:
        p_obs = p * params.p_slip / (p * params.p_slip + (1 - p) * (1 - params.p_guess))
    p_next = p_obs + (1 - p_obs) * params.p_learn
    return BKTState(p=max(0.0, min(1.0, p_next)), observations=state.observations + 1)


def replay(observations: Iterable[bool], params: BKTParams | None = None) -> BKTState:
    state = initial_state(params)
    for correct in observations:
        state = observe(state, correct, params)
    return state
