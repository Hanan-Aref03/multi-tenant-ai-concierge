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
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

import app.api.chat as chat_mod
from app.config import get_settings
from app.database import get_db
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

    with patch("app.services.origin_check.get_allowed_origins", side_effect=_get_origins):
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


@pytest.fixture
def mock_chat_runtime(monkeypatch):
    """Mock sidecars, DB, Redis, and router pipeline for /api/chat tests."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    guardrails = AsyncMock(return_value={
        "allowed": True,
        "decision": "allow",
        "reason": "ok",
        "redacted_message": "hello",
    })
    pipeline = AsyncMock(return_value={
        "reply": "Real pipeline reply",
        "intent": "knowledge_search",
        "action": None,
        "sources": [],
        "rag_confidence": 0.8,
    })

    monkeypatch.setattr(chat_mod, "_guardrails_check", guardrails)
    monkeypatch.setattr(chat_mod, "_get_redis", lambda: redis)
    monkeypatch.setattr(chat_mod, "_get_llm", lambda: None)
    monkeypatch.setattr(chat_mod, "_classifier_url", lambda: "http://modelserver:8010/v1")
    monkeypatch.setattr(chat_mod, "process_message", pipeline)

    yield SimpleNamespace(db=mock_db, redis=redis, guardrails=guardrails, pipeline=pipeline)
    app.dependency_overrides.pop(get_db, None)


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
async def test_chat_missing_token(mock_chat_runtime) -> None:
    """POST /api/chat with no Authorization header → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
        )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_chat_expired_token(mock_chat_runtime) -> None:
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
async def test_chat_tampered_token(mock_chat_runtime) -> None:
    """POST /api/chat with a forged/tampered token → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature"},
        )
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_chat_valid_token(mock_chat_runtime) -> None:
    """POST /api/chat with a valid token → 200."""
    token = _make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "reply" in data
    assert "[Agent stub]" not in data["reply"]
    mock_chat_runtime.guardrails.assert_awaited_once()
    mock_chat_runtime.pipeline.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_tenant_id_from_token_not_body(mock_chat_runtime) -> None:
    """Any tenant_id in the request body is ignored — only token claims used."""
    token = _make_token(tenant_id=TEST_TENANT_ID)
    evil_tenant_id = str(uuid.uuid4())
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
    kw = mock_chat_runtime.pipeline.call_args.kwargs
    assert kw["tenant_id"] == str(TEST_TENANT_ID)
    assert kw["tenant_id"] != evil_tenant_id


@pytest.mark.asyncio
async def test_chat_guardrails_blocked_returns_refusal(mock_chat_runtime) -> None:
    """Blocked messages return a safe refusal before routing/RAG/LLM."""
    mock_chat_runtime.guardrails.return_value = {
        "allowed": False,
        "decision": "block",
        "reason": "policy",
        "redacted_message": "blocked text",
    }
    token = _make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "bad"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["action"] == "blocked"
    assert "can't help" in data["reply"]
    mock_chat_runtime.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_chat_faq_support_uses_router_rag_path(mock_chat_runtime) -> None:
    mock_chat_runtime.pipeline.return_value = {
        "reply": "Grounded RAG answer",
        "intent": "knowledge_search",
        "action": None,
        "sources": [{"content_id": "doc1", "chunk_index": 0, "score": 0.9}],
        "rag_confidence": 0.9,
    }
    token = _make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "How does support work?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    assert res.json()["intent"] == "knowledge_search"
    assert res.json()["sources"]


@pytest.mark.asyncio
async def test_chat_human_request_routes_to_escalation(mock_chat_runtime) -> None:
    mock_chat_runtime.pipeline.return_value = {
        "reply": "I've flagged this conversation for our team.",
        "intent": "escalation",
        "action": "escalated",
        "sources": [],
        "rag_confidence": 0.0,
    }
    token = _make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "I need a human"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    assert res.json()["action"] == "escalated"


@pytest.mark.asyncio
async def test_chat_sales_routes_to_lead_capture_or_missing_info(mock_chat_runtime) -> None:
    mock_chat_runtime.pipeline.return_value = {
        "reply": "I can help with that. What is your name and email?",
        "intent": "lead_capture",
        "action": None,
        "sources": [],
        "rag_confidence": 0.0,
    }
    token = _make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": "Contact sales"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    assert res.json()["intent"] == "lead_capture"
    assert "email" in res.json()["reply"].lower()


@pytest.mark.asyncio
async def test_chat_sales_contact_uses_original_after_guardrails_redaction(mock_chat_runtime) -> None:
    mock_chat_runtime.guardrails.return_value = {
        "allowed": True,
        "decision": "allow",
        "reason": "ok",
        "redacted_message": "I want to buy. My name is Rayan and my email is [EMAIL]",
    }
    token = _make_token()
    message = "I want to buy. My name is Rayan and my email is rayan@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"conversation_id": str(TEST_CONVERSATION_ID), "message": message},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200, res.text
    assert mock_chat_runtime.pipeline.call_args.kwargs["message"] == message
