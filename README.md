# RTTune – Adaptive Retransmission Timeout Monitoring System

RTTune is a local academic Computer Networks project that demonstrates how an adaptive
Retransmission Timeout (RTO) estimator reacts to changing Round-Trip Time (RTT),
jitter, and packet loss.

## Features

- Experiment creation and persistent SQLite storage
- RTT simulation with configurable delay, jitter, and packet loss
- Manual RTT sampling
- RFC 6298-style SRTT / RTTVAR / RTO calculation
- Timeout and exponential RTO backoff
- Fixed-RTO vs adaptive-RTO comparison on the same generated RTT sequence
- Experiment history and experiment selection
- Measurement history
- Summary statistics
- RTT/RTO charts
- CSV exports
- Automated backend tests
- Swagger/OpenAPI documentation

## Technology

- Frontend: React + TypeScript + Vite + Recharts
- Backend: Python + FastAPI + SQLAlchemy
- Database: SQLite
- Runtime: Windows-friendly local deployment

## Algorithm

RTTune uses:

- alpha = 1/8
- beta = 1/4
- K = 4
- clock granularity G = 0.001 s
- demonstration MIN_RTO = 0.1 s
- MAX_RTO = 60 s

For the first RTT:

    SRTT = RTT
    RTTVAR = RTT / 2

For subsequent RTT samples:

    RTTVAR = (1-beta)*RTTVAR + beta*abs(SRTT_previous-RTT)
    SRTT   = (1-alpha)*SRTT + alpha*RTT

Then:

    RTO = SRTT + max(G, K*RTTVAR)

The implementation clamps RTO to the configured demonstration bounds.
After a timeout, RTO is doubled up to MAX_RTO.

## Run on Windows

### Backend

    cd backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    cd app
    uvicorn main:app --reload

Backend:
http://127.0.0.1:8000

Swagger:
http://127.0.0.1:8000/docs

### Frontend

Open another terminal:

    cd frontend
    npm install
    npm run dev

Frontend:
http://localhost:5173

## Run tests

From `backend` with the virtual environment active:

    pytest -q

## Project structure

    RTTune/
    ├── backend/
    │   ├── app/
    │   │   ├── core/
    │   │   ├── models/
    │   │   ├── services/
    │   │   └── main.py
    │   ├── tests/
    │   └── requirements.txt
    ├── frontend/
    │   ├── src/
    │   └── package.json
    └── docs/

This is a local single-user academic demonstration. The runtime estimator state is intentionally
kept in memory while experiment data is persisted in SQLite.
