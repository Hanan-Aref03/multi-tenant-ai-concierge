"""Tenant-scoped retrieval orchestration.

Mohammad owns RAG behavior and content grounding.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from services.rag.chunking import process_document
from services.rag.retrieval import retrieve, rerank
from apps.shared.llm_client import get_chat_model
from services.embeddings.client import get_embedding_client
from services.tracing import span

logger = logging.getLogger(__name__)


async def index_document(
    tenant_id: str,
    content_id: str,
    title: str,
    text: str,
    content_type: str,
    db_session,
    redis_client=None
) -> None:
    """
    Process document text into chunks, generate embeddings, and save to database.
    """
    logger.info("Indexing document: tenant=%s, content_id=%s, type=%s", tenant_id, content_id, content_type)
    
    # 1. Chunk the document
    chunks = process_document(text, tenant_id, content_id, content_type)
    if not chunks:
        logger.warning("No chunks generated for content_id=%s", content_id)
        return

    # 2. Extract texts to embed
    texts_to_embed = [chunk.text for chunk in chunks]
    
    # 3. Generate embeddings
    emb_client = get_embedding_client()
    embeddings = await emb_client.embed_texts(tenant_id, texts_to_embed, redis_client)

    # 4. Insert into the database
    # Assumes table `content_embeddings` has columns:
    # tenant_id, content_id, chunk_index, chunk_text, embedding, metadata
    sql_insert = """
        INSERT INTO app.content_chunks (tenant_id, document_id, chunk_index, content, embedding, metadata)
        VALUES (:tenant_id, :document_id, :chunk_index, :content, :embedding, :metadata);
    """
    
    from sqlalchemy import text as sa_text
    
    # Delete any existing embeddings first (for idempotency / updates)
    await delete_document_index(tenant_id, content_id, db_session)

    try:
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            metadata_json = json.dumps(chunk.metadata)
            await db_session.execute(
                sa_text(sql_insert),
                {
                    "tenant_id": tenant_id,
                    "document_id": content_id,
                    "chunk_index": idx,
                    "content": chunk.text,
                    "embedding": str(embedding),
                    "metadata": metadata_json
                }
            )
        logger.info("Successfully indexed %d chunks for content_id=%s", len(chunks), content_id)
    except Exception as e:
        logger.error("Failed to insert embeddings for content_id=%s: %s", content_id, e)
        raise e


async def delete_document_index(tenant_id: str, content_id: str, db_session) -> None:
    """
    Remove all chunk embeddings for a document from pgvector.
    """
    logger.info("Deleting document index: tenant=%s, content_id=%s", tenant_id, content_id)
    sql_delete = """
        DELETE FROM app.content_chunks
        WHERE tenant_id = :tenant_id AND document_id = :document_id;
    """
    from sqlalchemy import text as sa_text
    try:
        await db_session.execute(
            sa_text(sql_delete),
            {"tenant_id": tenant_id, "document_id": content_id}
        )
    except Exception as e:
        logger.error("Failed to delete embeddings for content_id=%s: %s", content_id, e)
        raise e


async def answer_from_knowledge(
    tenant_id: str,
    question: str,
    db_session,
    redis_client=None,
    llm_client=None  # Can be passed in / injected
) -> Dict[str, Any]:
    """
    Retrieve matching context chunks, build system prompt, and generate grounded answer.
    """
    logger.info("Generating grounded answer for tenant=%s, question=%s", tenant_id, question)

    with span("rag.answer", tenant_id=tenant_id) as rag_span:
        # 1. Retrieve raw matches
        raw_results = await retrieve(tenant_id, question, db_session, top_k=6, redis_client=redis_client)

        # 2. Rerank matches
        reranked_results = rerank(raw_results, max_results=3, score_threshold=0.65)
        rag_span.set_attribute("reranked_count", len(reranked_results))

        if not reranked_results:
            return {
                "answer": "I'm sorry, but I couldn't find any relevant information to answer your question.",
                "sources": [],
                "confidence": 0.0,
            }

        # 3. Construct context from reranked chunks
        context_str = "\n---\n".join(
            [f"Source {i+1}:\n{res.chunk_text}" for i, res in enumerate(reranked_results)]
        )

        # 4. Call LLM
        system_prompt = (
            "You are a helpful AI assistant. Answer the user's question using ONLY the provided context blocks. "
            "Do not use external knowledge or invent facts. If the context does not contain enough information, "
            "state that you do not know and suggest talking to a human.\n\n"
            f"Context:\n{context_str}"
        )

        answer_text = "Mocked answer using retrieved context."
        confidence = sum(res.score for res in reranked_results) / len(reranked_results)

        if llm_client:
            try:
                response = await llm_client.chat.completions.create(
                    model=get_chat_model(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                    temperature=0.0,
                )
                answer_text = response.choices[0].message.content
            except Exception as e:
                logger.error("LLM generation failed: %s", e)
                answer_text = "I encountered an error generating the answer, but here is what I found:\n" + context_str

        return {
            "answer": answer_text,
            "sources": [
                {"content_id": res.content_id, "chunk_index": res.chunk_index, "score": res.score}
                for res in reranked_results
            ],
            "confidence": confidence,
        }
