"""Chat API — receives visitor messages, dispatches to the agent (Owner B).

POST /api/chat — authenticated with widget session JWT
tenant_id is extracted exclusively from the verified token.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.widget_auth import WidgetTokenClaims, require_widget_token

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    # NOTE: any tenant_id field in the body is intentionally absent from this schema.
    # It is derived from the verified JWT only. Adding it here would be a security hole.


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    claims: WidgetTokenClaims = Depends(require_widget_token),
) -> ChatResponse:
    """Process a visitor chat message.

    tenant_id comes from the verified JWT claims — never from the request body.
    The agent integration (RAG, tool calling) is wired by Owner B.
    """
    # Verify conversation_id matches the token's conversation
    if body.conversation_id != str(claims.conversation_id):
        raise HTTPException(status_code=403, detail="Conversation ID mismatch")

    # Stub: Owner B wires the real agent here
    # The tenant_id (claims.tenant_id) scopes the agent's retrieval
    reply = f"[Agent stub] Received: {body.message!r} for tenant {claims.tenant_id}"

    return ChatResponse(reply=reply, conversation_id=body.conversation_id)
