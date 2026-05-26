"""Shared OpenTelemetry span helpers.

Mohammad owns all tracing instrumentation across the RAG/router/agent pipeline.

Usage (conditional import so the service works without opentelemetry installed):

    from services.tracing import span

    async with span("rag.retrieve", tenant_id=tenant_id) as s:
        results = await retrieve(...)
        s.set_attribute("result_count", len(results))
"""

import contextlib
import logging
from typing import Any, Generator

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode

    _tracer = trace.get_tracer("multi-tenant-ai-concierge")
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


class _NoopSpan:
    """Drop-in replacement when OpenTelemetry is not installed."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass


@contextlib.contextmanager
def span(name: str, tenant_id: str = "", **attributes: Any) -> Generator[Any, None, None]:
    """
    Context manager that starts an OTel span when opentelemetry is installed,
    or a no-op span otherwise.  Always sets ``tenant_id`` as an attribute.

    Example:
        async with span("router.classify", tenant_id=tid) as s:
            result = classify(...)
            s.set_attribute("intent", result.intent)
    """
    if not _OTEL_AVAILABLE:
        s = _NoopSpan()
        try:
            yield s
        except Exception as exc:
            s.record_exception(exc)
            raise
        return

    with _tracer.start_as_current_span(name) as otel_span:
        otel_span.set_attribute("tenant_id", tenant_id)
        for k, v in attributes.items():
            otel_span.set_attribute(k, str(v))
        try:
            yield otel_span
        except Exception as exc:
            otel_span.record_exception(exc)
            otel_span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
