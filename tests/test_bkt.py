import pytest

from testbridge.mastery.bkt import BKTParams, initial_state, observe, replay


def test_initial_state() -> None:
    state = initial_state()
    assert state.p == 0.3
    assert state.observations == 0


def test_correct_increases_and_incorrect_decreases() -> None:
    start = initial_state()
    after_correct = observe(start, True)
    after_wrong = observe(start, False)
    assert after_correct.p > start.p
    assert after_wrong.p < start.p
    assert after_correct.observations == 1


def test_replay_is_deterministic() -> None:
    one = replay([True, True, False])
    two = replay([True, True, False])
    assert one == two
    assert one.observations == 3


def test_replay_matches_known_probabilities() -> None:
    assert replay([True]).p == pytest.approx(0.7097560975609757)
    assert replay([True, True]).p == pytest.approx(0.9291914595729787)
    assert replay([True, True, False]).p == pytest.approx(0.6780697854016992)
    assert replay([False]).p == pytest.approx(0.19322033898305085)


def test_custom_params() -> None:
    params = BKTParams(p_init=0.5, p_learn=0.2, p_guess=0.1, p_slip=0.05)
    state = observe(initial_state(params), True, params)
    assert 0.0 <= state.p <= 1.0
