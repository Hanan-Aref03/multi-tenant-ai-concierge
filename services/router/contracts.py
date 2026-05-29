"""Router runtime data contracts."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClassifyResult:
    intent: str
    confidence: float
    source: str  # "classifier_server" | "llm" | "fallback"
    raw_intent: Optional[str] = None
    raw_route: Optional[str] = None


@dataclass
class RouteResult:
    reply: str
    intent: str
    confidence: float
    routed_to: str              # "direct" | "rag" | "agent"
    action: Optional[str]       # None | "lead_captured" | "escalated"
    sources: List[Dict[str, Any]] = field(default_factory=list)
    rag_confidence: float = 0.0
