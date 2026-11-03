"""Basic health endpoint tests."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "0.7.0"}


def test_empty_report_payload_is_validation_error():
    res = client.post("/report/summary", json={})
    assert res.status_code == 422
