from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_shutdown(monkeypatch) -> None:
    shutdown_called = False

    def fake_shutdown() -> None:
        nonlocal shutdown_called
        shutdown_called = True

    monkeypatch.setattr("app.main._shutdown_process", fake_shutdown)

    client = TestClient(app)
    response = client.post("/api/shutdown")

    assert response.status_code == 200
    assert response.json()["status"] == "shutting_down"
    assert shutdown_called
