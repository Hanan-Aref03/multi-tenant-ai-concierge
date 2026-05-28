"""Tests for widget origin enforcement and token auth — Owner D security gate.

These tests verify:
- 403 on disallowed origin at token exchange
- 403 on missing Origin header
- 401 on missing token to /api/chat
- 401 on expired/invalid token to /api/chat
- 200 on allowed origin + valid token (happy path)
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app

settings = get_settings()
ALLOWED_ORIGIN = "https://acme.com"
DISALLOWED_ORIGIN = "https://attacker.com"
TEST_WIDGET_ID = "test-widget-abc123"
TEST_TENANT_ID = uuid.uuid4()
TEST_CONVERSATION_ID = uuid.uuid4()


def _make_token(
    tenant_id: uuid.UUID = TEST_TENANT_ID,
    widget_id: str = TEST_WIDGET_ID,
    conversation_id: uuid.UUID = TEST_CONVERSATION_ID,
    origin: str = ALLOWED_ORIGIN,
    expire_delta: timedelta = timedelta(minutes=30),
) -> str:
    now = datetime.now(UTC)
    payload = {
        "tenant_id": str(tenant_id),
        "widget_id": widget_id,
        "conversation_id": str(conversation_id),
        "origin": origin,
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@pytest.fixture
def mock_origins():
    """Mock origin lookup to return controlled allowlist without DB."""
    async def _get_origins(widget_id: str, db) -> list:  # type: ignore[override]
        if widget_id == TEST_WIDGET_ID:
            return [ALLOWED_ORIGIN]
        return []

    with patch("app.api.widget.get_allowed_origins", side_effect=_get_origins), \
         patch("app.services.origin_check.get_allowed_origins", side_effect=_get_origins):
        yield


@pytest.fixture
def mock_widget_db():
    """Mock DB widget lookup."""
    from app.models.widget import Widget
    fake_widget = Widget()
    fake_widget.id = uuid.uuid4()
    fake_widget.tenant_id = TEST_TENANT_ID
    fake_widget.widget_id = TEST_WIDGET_ID
    fake_widget.greeting = "Hello!"
    fake_widget.accent_colour = "#3B82F6"
    fake_widget.allowed_origins = [ALLOWED_ORIGIN]

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = fake_widget

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.api.widget.get_db", return_value=iter([mock_db])):
        yield mock_db


@pytest.mark.asyncio
async def test_token_exchange_disallowed_origin(mock_origins) -> None:
    """POST /api/widget/token from disallowed origin → 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/widget/token",
            json={"widget_id": TEST_WIDGET_ID},
            headers={"Origin": DISALLOWED_ORIGIN},
        )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_token_exchange_missing_origin(mock_origins) -> None:
    """POST /api/widget/token with no Origin header → 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/widget/token",
            json={"widget_id": TEST_WIDGET_ID},
        )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_chat_missing_token() -> None:
    """POST /api/chat with no Authorization header → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
        )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_chat_expired_token() -> None:
    """POST /api/chat with an expired token → 401."""
    token = _make_token(expire_delta=timedelta(seconds=-1))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_chat_tampered_token() -> None:
    """POST /api/chat with a forged/tampered token → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature"},
        )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_chat_valid_token() -> None:
    """POST /api/chat with a valid token → 200."""
    token = _make_token()
    with patch("app.api.chat.process_message", AsyncMock(return_value={
        "reply": "Hello from the assistant.",
        "intent": "greeting",
        "action": None,
        "sources": [],
        "rag_confidence": 0.0,
    })):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/chat",
                json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
                headers={"Authorization": f"Bearer {token}"},
            )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["reply"] == "Hello from the assistant."


@pytest.mark.asyncio
async def test_chat_tenant_id_from_token_not_body() -> None:
    """Any tenant_id in the request body is ignored — only token claims used."""
    token = _make_token(tenant_id=TEST_TENANT_ID)
    evil_tenant_id = str(uuid.uuid4())
    def _reply(**kwargs):
        return {
            "reply": f"tenant={kwargs['tenant_id']}",
            "intent": "greeting",
            "action": None,
            "sources": [],
            "rag_confidence": 0.0,
        }

    with patch("app.api.chat.process_message", AsyncMock(side_effect=_reply)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/chat",
                # Sending extra field — FastAPI ignores unknown fields; token tenant_id wins
                json={
                    "conversation_id": str(TEST_CONVERSATION_ID),
                    "message": "hello",
                    "tenant_id": evil_tenant_id,  # must be ignored
                },
                headers={"Authorization": f"Bearer {token}"},
            )
    assert res.status_code == 200, res.text
    # The reply contains the correct tenant_id from the token, not the evil one
    assert evil_tenant_id not in res.json()["reply"] or str(TEST_TENANT_ID) in res.json()["reply"]
