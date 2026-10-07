# RTTune Algorithm

## 1. First measurement

For the first RTT sample:

SRTT = RTT

RTTVAR = RTT / 2

The initial RTO is then calculated from the RTO equation.

## 2. Subsequent measurement

RTTVAR is updated first using the previous SRTT:

RTTVAR = (1-beta)RTTVAR + beta|SRTT_previous - RTT|

Then SRTT is updated:

SRTT = (1-alpha)SRTT + alpha RTT

## 3. RTO

RTO = SRTT + max(G, K*RTTVAR)

RTTune uses:

alpha = 1/8
beta = 1/4
K = 4
G = 0.001 seconds

The demonstration RTO range is 0.1 to 60 seconds.

## 4. Timeout

A timeout doubles the current RTO:

RTO_new = min(2*RTO_old, 60)

This is the exponential backoff behavior demonstrated by RTTune.
