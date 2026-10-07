from pathlib import Path
import sys

TEST_DB = Path(__file__).resolve().parents[1] / "test_rttune.db"

# The application itself uses the normal SQLite database. These smoke tests
# exercise the live FastAPI application without requiring a separate service.
# They are intentionally small and deterministic at the API contract level.

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_root():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["name"] == "RTTune API"
