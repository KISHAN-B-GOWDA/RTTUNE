# RTTune Testing

## Unit tests

The RTO engine tests verify:

1. First-sample initialization.
2. Correct SRTT calculation.
3. Correct RTTVAR calculation using previous SRTT.
4. Minimum RTO enforcement.
5. Timeout doubling.
6. Maximum RTO enforcement.

Run:

    cd backend
    venv\Scripts\activate
    pytest -q

## Manual UI tests

### Test 1 – Manual RTT
Create an experiment and record 0.100, 0.120 and 0.090 seconds.
Verify SRTT, RTTVAR and RTO change after every sample.

### Test 2 – Simulation
Configure a base delay and jitter and run a simulation.
Verify measurements and charts populate.

### Test 3 – Packet loss
Set packet loss above zero and run the simulation.
Verify successful and lost packet counts are shown.

### Test 4 – Timeout backoff
Record an RTT and trigger timeout.
Verify RTO increases.

### Test 5 – Comparison
Run Fixed vs Adaptive comparison.
Verify both strategies use the same generated sequence and timeout counts
can differ according to the simulated conditions.

### Test 6 – Persistence
Create an experiment, restart the backend and reopen the frontend.
Verify the experiment remains in history.
