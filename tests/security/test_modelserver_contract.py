from fastapi.testclient import TestClient

from apps.modelserver.app.main import app


def test_modelserver_health_is_public() -> None:
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "modelserver"}


def test_modelserver_classify_requires_service_token() -> None:
    response = TestClient(app).post(
        "/v1/classify",
        json={"tenant_id": "tenant_a", "message": "hello"},
    )

    assert response.status_code == 401


def test_modelserver_classify_rejects_invalid_service_token(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    response = TestClient(app).post(
        "/v1/classify",
        headers={"Authorization": "Bearer wrong"},
        json={"tenant_id": "tenant_a", "message": "hello"},
    )

    assert response.status_code == 401


def test_modelserver_classify_returns_stub_with_request_id(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")
    client = TestClient(app)

    response = client.post(
        "/v1/classify",
        headers={
            "Authorization": "Bearer expected",
            "X-Request-ID": "req-owner-c-1",
        },
        json={"tenant_id": "tenant_a", "message": "hello"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-owner-c-1"
    assert response.json() == {
        "request_id": "req-owner-c-1",
        "route": "agent",
        "intent": "needs_agent_review",
        "confidence": 0.0,
        "model_version": "stub",
    }


def test_modelserver_classify_generates_request_id(monkeypatch) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    response = TestClient(app).post(
        "/v1/classify",
        headers={"Authorization": "Bearer expected"},
        json={"tenant_id": "tenant_a", "message": "hello"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
