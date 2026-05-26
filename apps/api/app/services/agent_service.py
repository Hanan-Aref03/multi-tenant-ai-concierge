"""Agent service — thin orchestration layer.

Mohammad owns the routing-to-agent integration.
Rayan owns the safety constraints that keep the agent bounded.

Delegates to:
  - services.router.router.route()  for classification, routing, and logging
  - services.agent.agent.run_agent()  for the bounded tool-calling loop
"""

import logging
from typing import Any, Dict, List, Optional

from services.agent.agent import run_agent
from services.router.router import route

logger = logging.getLogger(__name__)


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
    """
    Route a user message and return a reply.

    Delegates fully to services.router.router.route(), which handles:
    - Intent classification (model server → LLM → fallback)
    - Routing: direct (greeting/off_topic) / RAG (faq/knowledge_search) / agent
    - RAG-confidence fallback to agent
    - Routing decision logging

    Returns a dict with: reply, action, sources, rag_confidence.
    """
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
