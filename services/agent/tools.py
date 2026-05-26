"""Agent tools exposed to the assistant.

Mohammad owns the functional contract.
Hanan owns the side-effect boundaries for lead storage and escalation.

Only three tools are permitted: rag_search, capture_lead, escalate.
"""

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed tools (security guard — agent.py enforces this too)
# ---------------------------------------------------------------------------

ALLOWED_TOOLS = frozenset({"rag_search", "capture_lead", "escalate"})

# ---------------------------------------------------------------------------
# OpenAI function-calling schema definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "Search the tenant knowledge base for relevant information about products, "
                "services, policies, or FAQs. Always call this before answering substantive questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to run against the knowledge base.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_lead",
            "description": (
                "Save a visitor's contact information as a lead. "
                "Only call this when the user has willingly provided their name and email."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name of the visitor."},
                    "email": {"type": "string", "description": "Email address of the visitor."},
                    "phone": {"type": "string", "description": "Phone number (optional)."},
                    "notes": {"type": "string", "description": "Any additional context (optional)."},
                },
                "required": ["name", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": (
                "Escalate the conversation to a human team member. "
                "Use when you cannot resolve the query or the user asks for a human."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why the conversation is being escalated.",
                    }
                },
                "required": ["reason"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------


async def execute_tool(
    name: str,
    args: Dict[str, Any],
    *,
    tenant_id: str,
    session_id: str,
    db_session=None,
    redis_client=None,
    retrieval_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Dispatch a validated tool call and return its result as a plain dict.

    Parameters
    ----------
    name :
        Tool name — must be one of ALLOWED_TOOLS (caller must verify first).
    args :
        Parsed JSON arguments from the LLM tool call.
    tenant_id :
        Current tenant — all operations are scoped to this.
    session_id :
        Current session — used to scope lead and escalation records.
    db_session :
        Async SQLAlchemy session for persistence operations.
    redis_client :
        Optional Redis client for the embedding cache (rag_search only).
    retrieval_fn :
        Optional injection point for retrieve(). Defaults to the real
        ``services.rag.retrieval`` functions when None.
    """
    if name == "rag_search":
        return await _rag_search(
            args.get("query", ""),
            tenant_id=tenant_id,
            db_session=db_session,
            redis_client=redis_client,
            retrieval_fn=retrieval_fn,
        )

    if name == "capture_lead":
        return await _capture_lead(
            name_=args.get("name", ""),
            email=args.get("email", ""),
            phone=args.get("phone"),
            notes=args.get("notes"),
            tenant_id=tenant_id,
            session_id=session_id,
            db_session=db_session,
        )

    if name == "escalate":
        return await _escalate(
            reason=args.get("reason", "User requested escalation"),
            tenant_id=tenant_id,
            session_id=session_id,
            db_session=db_session,
        )

    # Should never reach here if caller enforces ALLOWED_TOOLS
    return {"error": f"Tool '{name}' is not permitted."}


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------


async def _rag_search(
    query: str,
    *,
    tenant_id: str,
    db_session,
    redis_client,
    retrieval_fn: Optional[Callable],
) -> Dict[str, Any]:
    if not query.strip():
        return {"results": [], "message": "Empty query provided."}

    try:
        if retrieval_fn is not None:
            results = await retrieval_fn(tenant_id, query, db_session, redis_client=redis_client)
        else:
            from services.rag.retrieval import retrieve, rerank
            raw = await retrieve(
                tenant_id, query, db_session, top_k=6, redis_client=redis_client
            )
            results = rerank(raw, max_results=3)

        if not results:
            return {"results": [], "message": "No relevant information found in the knowledge base."}

        formatted = [
            {
                "source": i + 1,
                "content_id": r.content_id,
                "chunk_index": r.chunk_index,
                "score": round(r.score, 4),
                "text": r.chunk_text,
            }
            for i, r in enumerate(results)
        ]
        return {"results": formatted}

    except Exception as exc:
        logger.error("rag_search failed for tenant=%s: %s", tenant_id, exc)
        return {"results": [], "error": "Knowledge base search failed."}


async def _capture_lead(
    *,
    name_: str,
    email: str,
    phone: Optional[str],
    notes: Optional[str],
    tenant_id: str,
    session_id: str,
    db_session,
) -> Dict[str, Any]:
    if not name_.strip() or not email.strip():
        return {"success": False, "error": "Both name and email are required to capture a lead."}

    if db_session is not None:
        try:
            from sqlalchemy import text as sa_text

            lead_id = str(uuid.uuid4())
            await db_session.execute(
                sa_text("""
                    INSERT INTO leads
                        (lead_id, tenant_id, full_name, email, phone, notes, session_id, status, created_at)
                    VALUES
                        (:lead_id, :tenant_id, :full_name, :email, :phone, :notes,
                         :session_id, 'new', NOW())
                    ON CONFLICT DO NOTHING;
                """),
                {
                    "lead_id": lead_id,
                    "tenant_id": tenant_id,
                    "full_name": name_.strip(),
                    "email": email.strip(),
                    "phone": phone,
                    "notes": notes,
                    "session_id": session_id,
                },
            )
            logger.info("Lead captured: tenant=%s session=%s lead_id=%s", tenant_id, session_id, lead_id)
        except Exception as exc:
            logger.error("Failed to persist lead for tenant=%s: %s", tenant_id, exc)
            return {"success": False, "error": "Database error while saving lead."}
    else:
        logger.warning("No db_session; lead not persisted (tenant=%s, name=%s)", tenant_id, name_)

    return {
        "success": True,
        "action": "lead_captured",
        "message": f"Contact information saved for {name_.strip()}. Someone from the team will be in touch.",
    }


async def _escalate(
    *,
    reason: str,
    tenant_id: str,
    session_id: str,
    db_session,
) -> Dict[str, Any]:
    if db_session is not None:
        try:
            from sqlalchemy import text as sa_text

            await db_session.execute(
                sa_text("""
                    UPDATE conversations
                    SET status = 'escalated',
                        updated_at = NOW()
                    WHERE tenant_id = :tenant_id
                      AND session_id = :session_id;
                """),
                {"tenant_id": tenant_id, "session_id": session_id},
            )
            logger.info("Conversation escalated: tenant=%s session=%s reason=%s", tenant_id, session_id, reason)
        except Exception as exc:
            logger.error("Failed to mark escalation for tenant=%s: %s", tenant_id, exc)

    return {
        "success": True,
        "action": "escalated",
        "message": (
            "I've flagged this conversation for our team. "
            "A member of the team will follow up with you shortly."
        ),
    }
