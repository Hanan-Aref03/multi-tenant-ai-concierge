"""Tenant-filtered vector retrieval.

Mohammad owns the retrieval logic and answer grounding.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from services.embeddings.client import get_embedding_client
from services.tracing import span

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single chunk returned by vector search."""

    chunk_text: str
    score: float
    content_id: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


async def retrieve(
    tenant_id: str,
    query: str,
    db_session,
    top_k: int = 5,
    redis_client=None,
    score_threshold: float = 0.35,
) -> List[RetrievalResult]:
    """Retrieve the top-k most relevant chunks for this tenant only."""
    client = get_embedding_client()
    try:
        query_embedding = await client.embed_text(tenant_id, query, redis_client)
    except Exception as exc:
        logger.warning(
            "Embedding unavailable for tenant=%s; falling back to lexical retrieval: %s",
            tenant_id,
            exc,
        )
        return await _retrieve_lexical(tenant_id, query, db_session, top_k=top_k)

    sql = """
        SELECT
            content AS chunk_text,
            document_id AS content_id,
            chunk_index,
            metadata,
            1 - (embedding <=> :query_vec) AS score
        FROM app.content_chunks
        WHERE tenant_id = :tid
        ORDER BY embedding <=> :query_vec
        LIMIT :k;
    """

    with span("rag.retrieve", tenant_id=tenant_id, top_k=top_k) as s:
        try:
            from sqlalchemy import text as sa_text

            result = await db_session.execute(
                sa_text(sql),
                {
                    "query_vec": str(query_embedding),
                    "tid": tenant_id,
                    "k": top_k,
                },
            )
            rows = result.fetchall()
        except Exception as exc:
            logger.error("Vector search failed for tenant=%s: %s", tenant_id, exc)
            return []

        results: List[RetrievalResult] = []
        for row in rows:
            score = float(row.score)
            if score < score_threshold:
                continue
            results.append(
                RetrievalResult(
                    chunk_text=row.chunk_text,
                    score=score,
                    content_id=row.content_id,
                    chunk_index=row.chunk_index,
                    metadata=row.metadata if row.metadata else {},
                )
            )

        s.set_attribute("result_count", len(results))

    logger.info(
        "Retrieval for tenant=%s returned %d results (top_k=%d, threshold=%.2f)",
        tenant_id,
        len(results),
        top_k,
        score_threshold,
    )

    return results


async def _retrieve_lexical(
    tenant_id: str,
    query: str,
    db_session,
    top_k: int,
) -> List[RetrievalResult]:
    """Tenant-filtered fallback retrieval for runtimes without embedding deps."""
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9]{3,}", query)[:6]]
    if not terms:
        return []

    where_clause = " OR ".join(f"lower(content) LIKE :term_{idx}" for idx, _ in enumerate(terms))
    sql = f"""
        SELECT
            content AS chunk_text,
            document_id AS content_id,
            chunk_index,
            metadata
        FROM app.content_chunks
        WHERE tenant_id = :tid
          AND ({where_clause})
        ORDER BY created_at DESC
        LIMIT :k;
    """
    params: Dict[str, Any] = {"tid": tenant_id, "k": top_k}
    params.update({f"term_{idx}": f"%{term}%" for idx, term in enumerate(terms)})

    try:
        from sqlalchemy import text as sa_text

        result = await db_session.execute(sa_text(sql), params)
        rows = result.fetchall()
    except Exception as exc:
        logger.error("Lexical retrieval failed for tenant=%s: %s", tenant_id, exc)
        return []

    results = [
        RetrievalResult(
            chunk_text=row.chunk_text,
            score=0.7,
            content_id=str(row.content_id),
            chunk_index=row.chunk_index,
            metadata=row.metadata if row.metadata else {},
        )
        for row in rows
    ]
    logger.info("Lexical retrieval for tenant=%s returned %d results", tenant_id, len(results))
    return results


def rerank(
    results: List[RetrievalResult],
    max_results: int = 3,
    score_threshold: float = 0.65,
) -> List[RetrievalResult]:
    """Deduplicate by content_id, then return the highest-confidence chunks."""
    filtered = [r for r in results if r.score >= score_threshold]
    logger.info("Rerank: %d chunks above threshold %.2f", len(filtered), score_threshold)

    best_per_doc: Dict[str, RetrievalResult] = {}
    for r in filtered:
        existing = best_per_doc.get(r.content_id)
        if existing is None or r.score > existing.score:
            best_per_doc[r.content_id] = r

    ranked = sorted(best_per_doc.values(), key=lambda x: x.score, reverse=True)
    return ranked[:max_results]
