"""Assistant service â€” thin orchestration layer for the backend runtime.

This mirrors the shared assistant wiring used elsewhere in the repo while
keeping the backend package self-contained.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.agent.agent import run_agent
from services.router.router import route


async def process_message(
    tenant_id: str,
    session_id: str,
    message: str,
    conversation_history: List[Dict],
    db_session,
    redis_client=None,
    llm_client=None,
    tenant_name: str = "the company",
    classifier_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Route an inbound visitor message and return the assistant reply."""

    async def _agent_fn(**kwargs):
        return await run_agent(tenant_name=tenant_name, **kwargs)

    result = await route(
        tenant_id=tenant_id,
        session_id=session_id,
        message=message,
        conversation_history=conversation_history,
        db_session=db_session,
        redis_client=redis_client,
        llm_client=llm_client,
        classifier_url=classifier_url,
        agent_fn=_agent_fn,
    )

    return {
        "reply": result.reply,
        "intent": result.intent,
        "action": result.action,
        "sources": result.sources,
        "rag_confidence": result.rag_confidence,
    }
