"""Integration test - full embed flow: token exchange -> chat -> rejection without token."""

import uuid
from datetime import UTC, datetime, timedelta
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
TEST_WIDGET_ID = "embed-test-widget"
TEST_TENANT_ID = uuid.uuid4()


def _token_for(conversation_id: uuid.UUID, expire: timedelta = timedelta(minutes=30)) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "tenant_id": str(TEST_TENANT_ID),
            "widget_id": TEST_WIDGET_ID,
            "conversation_id": str(conversation_id),
            "origin": ALLOWED_ORIGIN,
            "iat": int(now.timestamp()),
            "exp": int((now + expire).timestamp()),
        },
        settings.secret_key,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_full_embed_flow() -> None:
    """End-to-end: loader gets token -> chat message accepted."""
    conversation_id = uuid.uuid4()
    token = _token_for(conversation_id)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch.object(
            chat_mod,
            "_guardrails_check",
            AsyncMock(
                return_value={
                    "allowed": True,
                    "decision": "allow",
                    "reason": "ok",
                    "redacted_message": "hello",
                }
            ),
        ), patch.object(chat_mod, "_get_redis", return_value=None), patch.object(
            chat_mod, "_get_llm", return_value=None
        ), patch.object(
            chat_mod, "_classifier_url", return_value="http://modelserver:8010/v1"
        ), patch.object(
            chat_mod,
            "process_message",
            AsyncMock(
                return_value={
                    "reply": "Hello from the assistant.",
                    "intent": "knowledge_search",
                    "action": None,
                    "sources": [],
                    "rag_confidence": 0.0,
                }
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post(
                    "/api/chat",
                    json={"conversation_id": str(conversation_id), "message": "hello"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert res.status_code == 200
                assert res.json()["conversation_id"] == str(conversation_id)
                assert res.json()["reply"] == "Hello from the assistant."
                assert res.json()["intent"] == "knowledge_search"

                res2 = await client.post(
                    "/api/chat",
                    json={"conversation_id": str(conversation_id), "message": "hello"},
                )
                assert res2.status_code == 401

                expired = _token_for(conversation_id, expire=timedelta(seconds=-1))
                res3 = await client.post(
                    "/api/chat",
                    json={"conversation_id": str(conversation_id), "message": "hello"},
                    headers={"Authorization": f"Bearer {expired}"},
                )
                assert res3.status_code == 401

        mock_db.execute.assert_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)
