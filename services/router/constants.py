"""Router constants and compiled patterns."""

import re
from typing import Dict

INTENTS = frozenset({"greeting", "faq", "knowledge_search", "lead_capture", "escalation", "off_topic", "spam"})

MODELSERVER_INTENT_MAP: Dict[str, str] = {
    "faq": "faq",
    "support": "knowledge_search",
    "sales_or_leads": "lead_capture",
    "human_request": "escalation",
    "spam": "spam",
    "other": "knowledge_search",
}

# Below this classifier confidence -> always route to agent (4A.2)
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.7

# Below this RAG answer confidence -> fall through to agent (4A.2)
RAG_CONFIDENCE_THRESHOLD = 0.5

SALES_KEYWORDS = (
    "pricing",
    "buy",
    "interested",
    "contact me",
    "sales representative",
    "my email is",
    "my name is",
    "quote",
    "demo",
)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
NAME_RE = re.compile(
    r"\bmy name is\s+([A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3})",
    re.IGNORECASE,
)

_DIRECT_REPLIES: Dict[str, str] = {
    "greeting": "Hello! How can I help you today?",
    "spam": "I can't help with that request. If you need help with our products or services, please send a clear question.",
    "off_topic": (
        "I'm here to help with questions about our products and services. "
        "Is there anything I can assist you with in that area?"
    ),
}
