"""Direct lead capture path."""

import json
import logging
import uuid
from typing import Any, Dict

from services.router.lead_utils import _extract_contact

logger = logging.getLogger(__name__)


async def _capture_lead_direct(
    *,
    tenant_id: str,
    session_id: str,
    message: str,
    db_session,
) -> Dict[str, Any]:
    contact = _extract_contact(message)
    email = contact["email"]
    phone = contact["phone"]

    missing = []
    if not email and not phone:
        missing.append("email or phone number")
    if missing:
        return {
            "reply": f"I can help with that. Please share your {' and '.join(missing)} so our team can contact you.",
            "action": None,
        }

    if db_session is not None:
        try:
            from sqlalchemy import text as sa_text

            lead_id = str(uuid.uuid4())
            params = {
                "lead_id": lead_id,
                "tenant_id": tenant_id,
                "conversation_id": session_id,
                "full_name": contact["name"] or "Website visitor",
                "email": email or "",
                "phone": phone,
                "message": message,
                "metadata": json.dumps({
                    "phone": phone,
                    "conversation_id": session_id,
                    "intent": "lead_capture",
                    "message": message,
                }),
            }
            try:
                await db_session.execute(
                    sa_text("""
                        INSERT INTO app.leads
                            (lead_id, tenant_id, full_name, email, intent, source, status, metadata, created_at)
                        VALUES
                            (:lead_id, :tenant_id, :full_name, :email, 'sales_or_leads',
                             'widget', 'new', :metadata, NOW());
                    """),
                    params,
                )
            except Exception:
                if hasattr(db_session, "rollback"):
                    await db_session.rollback()
                await db_session.execute(
                    sa_text("""
                        CREATE TABLE IF NOT EXISTS public.leads (
                            lead_id uuid PRIMARY KEY,
                            tenant_id uuid NOT NULL,
                            conversation_id uuid NOT NULL,
                            full_name text NOT NULL,
                            email text NOT NULL,
                            phone text,
                            intent text NOT NULL,
                            message text NOT NULL,
                            source text NOT NULL DEFAULT 'widget',
                            status text NOT NULL DEFAULT 'new',
                            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                            created_at timestamptz NOT NULL DEFAULT now()
                        );
                    """)
                )
                await db_session.execute(
                    sa_text("""
                        INSERT INTO public.leads
                            (lead_id, tenant_id, conversation_id, full_name, email, phone,
                             intent, message, source, status, metadata, created_at)
                        VALUES
                            (:lead_id, :tenant_id, :conversation_id, :full_name, :email, :phone,
                             'sales_or_leads', :message, 'widget', 'new', :metadata, NOW());
                    """),
                    params,
                )
            if hasattr(db_session, "commit"):
                await db_session.commit()
            logger.info("Lead captured directly: tenant=%s session=%s lead_id=%s", tenant_id, session_id, lead_id)
        except Exception as exc:
            logger.error("Direct lead capture failed for tenant=%s session=%s: %s", tenant_id, session_id, exc)
            return {
                "reply": "I have your request, but I could not save the lead right now. Let me connect you with our team.",
                "action": "escalated",
            }

    display_name = contact["name"] or "there"
    return {
        "reply": f"Thanks {display_name}, I captured your request and our team will contact you.",
        "action": "lead_captured",
    }
