"""Tenant-scoped content models.

Mohammad owns tenant-scoped content indexing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentKind(str, Enum):
    """Broad content categories used by the RAG pipeline."""

    DOCUMENT = "document"
    FAQ = "faq"
    POLICY = "policy"
    PRODUCT = "product"


@dataclass(slots=True)
class ContentChunk:
    """A tenant-scoped chunk ready for embeddings and retrieval."""

    tenant_id: str
    document_id: str
    chunk_id: str
    chunk_index: int
    content: str
    embedding: tuple[float, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class ContentDocument:
    """A document uploaded by one tenant."""

    tenant_id: str
    document_id: str
    title: str
    body: str
    source_uri: str | None = None
    kind: ContentKind = ContentKind.DOCUMENT
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[ContentChunk] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def add_chunk(self, chunk: ContentChunk) -> ContentChunk:
        if chunk.tenant_id != self.tenant_id or chunk.document_id != self.document_id:
            raise ValueError("Content chunk does not belong to this document")
        self.chunks = [existing for existing in self.chunks if existing.chunk_id != chunk.chunk_id]
        self.chunks.append(chunk)
        self.touch()
        return chunk
