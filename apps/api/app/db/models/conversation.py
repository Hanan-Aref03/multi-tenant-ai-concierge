"""Conversation table model placeholder.

Mohammad owns the conversation flow.
Hanan owns the tenant-safe persistence boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationStatus(str, Enum):
    """Lifecycle states for a visitor conversation."""

    OPEN = "open"
    ESCALATED = "escalated"
    CLOSED = "closed"


class MessageRole(str, Enum):
    """Message author roles stored in the transcript."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True)
class ConversationMessage:
    """One message in a tenant-scoped transcript."""

    tenant_id: str
    conversation_id: str
    message_id: str
    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class Conversation:
    """A tenant-scoped assistant conversation."""

    tenant_id: str
    conversation_id: str
    visitor_id: str
    source_origin: str | None = None
    status: ConversationStatus = ConversationStatus.OPEN
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        if message.tenant_id != self.tenant_id or message.conversation_id != self.conversation_id:
            raise ValueError("Conversation message does not belong to this conversation")
        self.messages = [existing for existing in self.messages if existing.message_id != message.message_id]
        self.messages.append(message)
        self.touch()
        return message

    def escalate(self, reason: str, details: dict[str, Any] | None = None) -> None:
        self.status = ConversationStatus.ESCALATED
        self.metadata["escalation_reason"] = reason
        if details:
            self.metadata["escalation_details"] = details
        self.touch()
