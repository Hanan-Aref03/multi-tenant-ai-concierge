"""Tenant-filtered vector retrieval.

Mohammad owns the retrieval logic and answer grounding.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

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


# ---------------------------------------------------------------------------
# Core retrieval
# ---------------------------------------------------------------------------

async def retrieve(
    tenant_id: str,
    query: str,
    db_session,
    top_k: int = 5,
    redis_client=None,
    score_threshold: float = 0.35,
) -> List[RetrievalResult]:
    """
    Retrieve the top-k most relevant chunks for *this tenant only*.

    Flow:
        1. Embed the query using the shared EmbeddingClient.
        2. Run a cosine-similarity search on pgvector, **always filtered
           by tenant_id** (defense-in-depth: the RLS policy Hanan sets
           on content_embeddings enforces this at the DB layer too).
        3. Filter out results below ``score_threshold``.
        4. Return ranked results.

    Parameters
    ----------
    tenant_id : str
        The tenant whose knowledge base to search.
    query : str
        The visitor / user question.
    db_session :
        An async SQLAlchemy session (provided by Hanan's session helper).
        The session must already have ``SET app.tenant_id`` so RLS applies.
    top_k : int
        Maximum number of chunks to return.
    redis_client :
        Optional async Redis client for the embedding cache.
    score_threshold : float
        Minimum cosine-similarity score to keep a result.
        MiniLM-L6-v2 cosine scores are typically in the 0.2–0.8 range,
        so 0.35 is a reasonable floor for high recall.
    """

    # 1. Embed the query ------------------------------------------------
    client = get_embedding_client()
    try:
        query_embedding = await client.embed_text(tenant_id, query, redis_client)
    except RuntimeError as exc:
        logger.warning(
            "Embedding client unavailable for tenant=%s; returning no retrieval results: %s",
            tenant_id,
            exc,
        )
        return []
    except Exception as exc:
        logger.warning(
            "Embedding generation failed for tenant=%s; returning no retrieval results: %s",
            tenant_id,
            exc,
        )
        return []

    # 2. Vector search via pgvector ------------------------------------
    sql = """
        SELECT
            content   AS chunk_text,
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

        # 3. Build results & apply threshold --------------------------------
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


# ---------------------------------------------------------------------------
# Reranking (step 2D.2)
# ---------------------------------------------------------------------------

def rerank(
    results: List[RetrievalResult],
    max_results: int = 3,
    score_threshold: float = 0.65,
) -> List[RetrievalResult]:
    """
    Simple reranker that deduplicates by content_id, applies a higher
    confidence threshold, and returns the top ``max_results``.

    This satisfies the "simple relevance scoring" approach from the brief.
    For production use, a cross-encoder (e.g., sentence-transformers) can
    be plugged in here to re-score each (query, chunk) pair and then filter
    by a higher threshold like 0.65.

    Parameters
    ----------
    results : list[RetrievalResult]
        The initial retrieval results (usually from ``retrieve()``).
    max_results : int
        Maximum number of unique documents to return after deduplication.
    score_threshold : float
        Minimum cosine similarity score to keep after reranking.
        Set to 0.65 as a stricter post-filter.
    """
    # 1. Apply the stricter threshold (post-retrieval confidence filter)
    filtered = [r for r in results if r.score >= score_threshold]
    logger.info("Rerank: %d chunks above threshold %.2f", len(filtered), score_threshold)

    # 2. Deduplicate by content_id (keep highest score per document)
    best_per_doc: Dict[str, RetrievalResult] = {}
    for r in filtered:
        existing = best_per_doc.get(r.content_id)
        if existing is None or r.score > existing.score:
            best_per_doc[r.content_id] = r

    # 3. Sort by score descending and cap
    ranked = sorted(best_per_doc.values(), key=lambda x: x.score, reverse=True)
    return ranked[:max_results]
