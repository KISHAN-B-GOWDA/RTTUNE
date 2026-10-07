from dataclasses import dataclass


@dataclass
class RTOState:
    srtt: float | None = None
    rttvar: float | None = None
    rto: float = 1.0


class RTOEstimator:
    """
    Adaptive Retransmission Timeout estimator.

    RTT values are represented in seconds.

    The estimator follows the RFC 6298-style
    SRTT / RTTVAR / RTO calculation:

        SRTT = (1 - alpha) * SRTT + alpha * RTT

        RTTVAR = (1 - beta) * RTTVAR
                 + beta * abs(SRTT_previous - RTT)

        RTO = SRTT + max(G, K * RTTVAR)

    RTTune uses alpha=1/8, beta=1/4, K=4.
    A 100 ms minimum is used as a demonstration bound so
    timeout behavior remains visible in local simulations.
    """

    ALPHA = 1 / 8
    BETA = 1 / 4
    K = 4
    CLOCK_GRANULARITY = 0.001

    MIN_RTO = 0.1
    MAX_RTO = 60.0

    def __init__(self):
        self.state = RTOState()

    def update(self, rtt: float) -> RTOState:
        if rtt <= 0:
            raise ValueError("RTT must be greater than zero.")

        if self.state.srtt is None:
            self.state.srtt = rtt
            self.state.rttvar = rtt / 2
        else:
            assert self.state.rttvar is not None
            previous_srtt = self.state.srtt

            self.state.rttvar = (
                (1 - self.BETA) * self.state.rttvar
                + self.BETA * abs(previous_srtt - rtt)
            )

            self.state.srtt = (
                (1 - self.ALPHA) * previous_srtt
                + self.ALPHA * rtt
            )

        self.state.rto = self._calculate_rto()
        return self.state

    def timeout_backoff(self) -> RTOState:
        self.state.rto = min(
            self.state.rto * 2,
            self.MAX_RTO,
        )
        return self.state

    def _calculate_rto(self) -> float:
        if self.state.srtt is None or self.state.rttvar is None:
            return self.state.rto

        rto = self.state.srtt + max(
            self.CLOCK_GRANULARITY,
            self.K * self.state.rttvar,
        )

        return max(
            self.MIN_RTO,
            min(rto, self.MAX_RTO),
        )

    def get_state(self) -> dict:
        return {
            "srtt": self.state.srtt,
            "rttvar": self.state.rttvar,
            "rto": self.state.rto,
        }
