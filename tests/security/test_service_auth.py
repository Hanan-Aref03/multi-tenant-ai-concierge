import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.shared.service_auth import (
    LOCAL_TEST_SERVICE_TOKEN,
    get_service_token,
    require_service_token,
)


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_service_token)])
    def protected() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_service_token_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "from-env")

    assert get_service_token() == "from-env"


def test_service_token_uses_default_only_under_pytest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/security/test_service_auth.py")

    assert get_service_token() == LOCAL_TEST_SERVICE_TOKEN


def test_service_token_fails_closed_without_env_outside_pytest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(RuntimeError):
        get_service_token()


def test_auth_dependency_rejects_missing_token() -> None:
    response = _client().get("/protected")

    assert response.status_code == 401


def test_auth_dependency_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    response = _client().get(
        "/protected",
        headers={"Authorization": "Bearer wrong"},
    )

    assert response.status_code == 401


def test_auth_dependency_accepts_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_TOKEN", "expected")

    response = _client().get(
        "/protected",
        headers={"Authorization": "Bearer expected"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
