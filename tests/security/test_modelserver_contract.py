from fastapi.testclient import TestClient

from apps.modelserver.app.main import app


def test_modelserver_health_is_public() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "modelserver"}


def test_modelserver_health_contract_reports_model_state() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_checksum_valid"] is True


def test_modelserver_classify_requires_service_token() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/classify",
            json={"tenant_id": "tenant_a", "message": "hello"},
        )

    assert response.status_code == 401


def test_modelserver_classify_rejects_invalid_service_token(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    with TestClient(app) as client:
        response = client.post(
            "/v1/classify",
            headers={"Authorization": "Bearer wrong"},
            json={"tenant_id": "tenant_a", "message": "hello"},
        )

    assert response.status_code == 401


def test_modelserver_classify_returns_prediction_with_request_id(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    with TestClient(app) as client:
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
    body = response.json()
    assert body["request_id"] == "req-owner-c-1"
    assert body["route"] in {
        "agent",
        "capture_lead",
        "drop",
        "escalate",
        "rag",
        "support",
    }
    assert body["intent"] in {
        "faq",
        "human_request",
        "other",
        "sales_or_leads",
        "spam",
        "support",
    }
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["model_version"] != "stub"


def test_modelserver_classify_generates_request_id(monkeypatch) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    with TestClient(app) as client:
        response = client.post(
            "/v1/classify",
            headers={"Authorization": "Bearer expected"},
            json={"tenant_id": "tenant_a", "message": "hello"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
