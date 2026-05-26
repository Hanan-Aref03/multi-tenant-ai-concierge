import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.admin import _get_or_create_config, _get_or_create_widget, _widget_response
from app.models.widget import Widget


@pytest.mark.asyncio
async def test_admin_widget_seeds_local_defaults(monkeypatch):
    monkeypatch.setenv("WIDGET_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    widget = await _get_or_create_widget(tenant_id, db)

    assert widget.widget_id == "tenant-00000000-widget"
    assert widget.allowed_origins == ["http://localhost:3000", "http://localhost:5173"]
    db.add.assert_called_once()
    assert db.commit.await_count == 1
    assert db.refresh.await_count == 1


@pytest.mark.asyncio
async def test_admin_config_seeds_defaults():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    cfg = await _get_or_create_config(tenant_id, db)

    assert cfg.agent_persona == "You are a helpful assistant."
    assert cfg.enabled_tools == ["rag_search", "capture_lead", "escalate"]
    assert db.commit.await_count == 1
    assert db.refresh.await_count == 1


def test_widget_response_includes_public_api_base(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")

    widget = Widget()
    widget.widget_id = "tenant-00000000-widget"
    widget.greeting = "Hi!"
    widget.accent_colour = "#3B82F6"
    widget.allowed_origins = ["http://localhost:3000"]

    response = _widget_response(widget)

    assert response.widget_id == widget.widget_id
    assert 'data-api-base="http://localhost:8000"' in response.embed_snippet
