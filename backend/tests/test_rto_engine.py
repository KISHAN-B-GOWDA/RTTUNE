import math

from app.services.rto_engine import RTOEstimator


def test_first_sample_initializes_state():
    e = RTOEstimator()
    state = e.update(0.1)

    assert math.isclose(state.srtt, 0.1)
    assert math.isclose(state.rttvar, 0.05)
    assert math.isclose(state.rto, 0.3)


def test_second_sample_uses_previous_srtt_for_rttvar():
    e = RTOEstimator()
    e.update(0.1)
    state = e.update(0.12)

    assert math.isclose(state.srtt, 0.1025)
    assert math.isclose(state.rttvar, 0.0425)
    assert math.isclose(state.rto, 0.2725)


def test_minimum_rto_is_applied():
    e = RTOEstimator()
    state = e.update(0.001)

    assert state.rto == RTOEstimator.MIN_RTO


def test_timeout_doubles_rto():
    e = RTOEstimator()
    e.update(0.1)

    before = e.state.rto
    after = e.timeout_backoff().rto

    assert math.isclose(after, min(before * 2, RTOEstimator.MAX_RTO))


def test_timeout_never_exceeds_maximum():
    e = RTOEstimator()
    e.state.rto = RTOEstimator.MAX_RTO
    state = e.timeout_backoff()

    assert state.rto == RTOEstimator.MAX_RTO
