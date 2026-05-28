"""Bounded tool-calling agent.

Mohammad owns the orchestration loop.
Rayan owns the safety rails around it.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from services.agent.tools import ALLOWED_TOOLS, TOOL_DEFINITIONS, execute_tool
from apps.shared.llm_client import get_chat_model
from services.tracing import span

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 5          # hard cap on tool-call rounds (4B.1, ROUT-07)
MAX_HISTORY_MESSAGES = 10   # messages kept in context (4B.3)
MAX_HISTORY_CHARS = 12_000  # ~3 000 tokens; older messages trimmed first (4B.3)
MEMORY_TTL_SECONDS = 1_800  # 30 min Redis TTL (matches Phase 3 spec)

_FALLBACK_REPLY = (
    "I wasn't able to fully resolve your request. "
    "Let me connect you with a member of our team who can help you directly."
)

# ---------------------------------------------------------------------------
# System prompt loader
# ---------------------------------------------------------------------------


def _load_system_prompt(tenant_name: str = "the company") -> str:
    """Read prompts/agent/tool_use.md and substitute the tenant name."""
    prompt_path = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "prompts", "agent", "tool_use.md",
        )
    )
    try:
        with open(prompt_path) as f:
            return f.read().replace("{{tenant_name}}", tenant_name)
    except OSError:
        logger.warning("Could not load agent tool_use.md prompt; using inline fallback")
        return (
            f"You are a helpful customer support AI for {tenant_name}. "
            "You have three tools: rag_search, capture_lead, escalate. "
            "Only use these tools. Search before answering questions."
        )


# ---------------------------------------------------------------------------
# Conversation memory helpers (4B.3)
# ---------------------------------------------------------------------------


def _trim_history(
    messages: List[Dict],
    max_messages: int = MAX_HISTORY_MESSAGES,
    max_chars: int = MAX_HISTORY_CHARS,
) -> List[Dict]:
    """
    Keep at most *max_messages* and ensure total content fits in *max_chars*.
    Trims oldest messages first so recent context is always preserved.
    """
    trimmed = messages[-max_messages:] if len(messages) > max_messages else list(messages)

    while len(trimmed) > 1:
        total = sum(len(str(m.get("content") or "")) for m in trimmed)
        if total <= max_chars:
            break
        trimmed = trimmed[1:]

    return trimmed


async def _load_memory(
    tenant_id: str,
    session_id: str,
    redis_client,
    provided_history: List[Dict],
) -> List[Dict]:
    """
    Load conversation history from Redis and merge with the caller-supplied list.

    Redis is the authoritative store; provided_history is used as a fallback
    when Redis is unavailable so the agent still has context.
    """
    if redis_client is None:
        return _trim_history(provided_history)

    redis_key = f"conv:{tenant_id}:{session_id}"
    try:
        raw = await redis_client.get(redis_key)
        if raw:
            stored: List[Dict] = json.loads(raw)
            # Stored history is more complete; use it and append anything new
            # that the caller provided beyond what is stored.
            stored_len = len(stored)
            extra = provided_history[stored_len:] if len(provided_history) > stored_len else []
            merged = stored + extra
            return _trim_history(merged)
    except Exception as exc:
        logger.warning("Failed to load conversation memory from Redis (%s); using provided history", exc)

    return _trim_history(provided_history)


async def _save_memory(
    tenant_id: str,
    session_id: str,
    redis_client,
    history: List[Dict],
    new_messages: List[Dict],
) -> None:
    """Append *new_messages* to *history* and persist back to Redis."""
    if redis_client is None:
        return

    updated = _trim_history(history + new_messages)
    redis_key = f"conv:{tenant_id}:{session_id}"
    try:
        await redis_client.set(redis_key, json.dumps(updated), ex=MEMORY_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Failed to save conversation memory to Redis (%s)", exc)


# ---------------------------------------------------------------------------
# Message format helpers
# ---------------------------------------------------------------------------


def _assistant_msg_to_dict(msg) -> Dict[str, Any]:
    """Convert an OpenAI SDK assistant message object to a plain dict."""
    d: Dict[str, Any] = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


# ---------------------------------------------------------------------------
# Main bounded agent loop (4B.1 + 4B.2)
# ---------------------------------------------------------------------------


async def run_agent(
    tenant_id: str,
    session_id: str,
    message: str,
    conversation_history: List[Dict],
    intent: str = "knowledge_search",
    db_session=None,
    redis_client=None,
    llm_client=None,
    tenant_name: str = "the company",
    max_iterations: int = MAX_ITERATIONS,
    retrieval_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Run the bounded tool-calling agent loop.

    The agent is given *max_iterations* rounds to call tools and produce a
    final answer. If the limit is reached without a text reply, a graceful
    handoff message is returned (ROUT-07).

    Parameters
    ----------
    tenant_id :
        Scopes all tool calls and memory to this tenant.
    session_id :
        Identifies the conversation for memory and side effects.
    message :
        The user's current message.
    conversation_history :
        Recent turns provided by the caller (supplemented by Redis memory).
    intent :
        The classified intent forwarded by the router — helps the agent
        prioritise the right tool on the first iteration.
    db_session :
        Async SQLAlchemy session for persistence operations.
    redis_client :
        Optional Redis client for memory and embedding cache.
    llm_client :
        OpenAI-compatible async client with .chat.completions.create().
    tenant_name :
        Display name substituted into the system prompt.
    max_iterations :
        Hard cap on tool-call rounds (default 5).
    retrieval_fn :
        Optional injection for rag_search (used in tests).

    Returns
    -------
    dict with keys: reply, action, sources, rag_confidence
    """
    if llm_client is None:
        logger.warning("No LLM client provided to run_agent; returning fallback reply")
        return {"reply": _FALLBACK_REPLY, "action": None, "sources": [], "rag_confidence": 0.0}

    # 4B.3: Load memory --------------------------------------------------
    history = await _load_memory(tenant_id, session_id, redis_client, conversation_history)

    system_prompt = _load_system_prompt(tenant_name)
    messages: List[Dict] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    accumulated_sources: List[Dict] = []
    final_action: Optional[str] = None

    # 4B.2: Agent loop ---------------------------------------------------
    with span("agent.loop", tenant_id=tenant_id, session_id=session_id, intent=intent) as loop_span:
        for iteration in range(max_iterations):
            logger.info(
                "Agent iteration %d/%d tenant=%s session=%s",
                iteration + 1, max_iterations, tenant_id, session_id,
            )

            try:
                response = await llm_client.chat.completions.create(
                    model=get_chat_model(),
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.0,
                )
            except Exception as exc:
                logger.error("LLM call failed in agent loop (iteration=%d): %s", iteration + 1, exc)
                break

            choice = response.choices[0]
            msg = choice.message

            # No tool calls → final text answer ------------------------------
            if not msg.tool_calls:
                reply = msg.content or ""
                loop_span.set_attribute("iterations", iteration + 1)
                await _save_memory(
                    tenant_id, session_id, redis_client, history,
                    [{"role": "user", "content": message}, {"role": "assistant", "content": reply}],
                )
                return {
                    "reply": reply,
                    "action": final_action,
                    "sources": accumulated_sources,
                    "rag_confidence": 0.0,
                }

            # Append assistant message with tool calls -----------------------
            assistant_dict = _assistant_msg_to_dict(msg)
            messages.append(assistant_dict)

            # Execute each tool call -----------------------------------------
            for tc in msg.tool_calls:
                tool_name = tc.function.name

                # Security: reject any tool not on the approved list (ROUT-04)
                if tool_name not in ALLOWED_TOOLS:
                    logger.warning(
                        "Agent tried to call unapproved tool '%s' (tenant=%s) — blocked",
                        tool_name, tenant_id,
                    )
                    tool_result = {"error": f"Tool '{tool_name}' is not permitted."}
                else:
                    with span("agent.tool_call", tenant_id=tenant_id, tool=tool_name):
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        tool_result = await execute_tool(
                            tool_name,
                            args,
                            tenant_id=tenant_id,
                            session_id=session_id,
                            db_session=db_session,
                            redis_client=redis_client,
                            retrieval_fn=retrieval_fn,
                        )

                    # Track side-effects and sources
                    if tool_result.get("action"):
                        final_action = tool_result["action"]

                    if tool_name == "rag_search":
                        accumulated_sources.extend(tool_result.get("results", []))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result),
                })

        loop_span.set_attribute("iterations", max_iterations)

    # 4B.1: Max iterations reached — graceful exit (ROUT-07) ------------
    logger.warning(
        "Agent reached max_iterations=%d without final answer (tenant=%s session=%s)",
        max_iterations, tenant_id, session_id,
    )
    await _save_memory(
        tenant_id, session_id, redis_client, history,
        [
            {"role": "user", "content": message},
            {"role": "assistant", "content": _FALLBACK_REPLY},
        ],
    )
    return {
        "reply": _FALLBACK_REPLY,
        "action": final_action or "escalated",
        "sources": accumulated_sources,
        "rag_confidence": 0.0,
    }
