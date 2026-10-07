# RTTune Backend

FastAPI service for the RTTune adaptive retransmission timeout project.

Run:

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    cd app
    uvicorn main:app --reload

Swagger:
http://127.0.0.1:8000/docs

Tests:

    cd ..
    pytest -q
