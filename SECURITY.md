# Security Notes — Concierge Widget Auth

## Threat Model: Widget Authentication

### The Boundary

**The signed JWT is the auth boundary. CORS and CSP are defense-in-depth.**

CORS and `Content-Security-Policy: frame-ancestors` are browser-enforced controls.
They stop browser-based embedding on disallowed origins. They do **nothing** to stop:
- A `curl` request with a copied `widget_id`
- A server-side caller that ignores CORS
- A browser extension that strips CORS headers

The token exchange endpoint (`POST /api/widget/token`) validates the `Origin` header
**server-side** and rejects non-browser callers that lack or forge an allowed origin.
Every chat request then carries the signed token — the API verifies signature + expiry
before processing any message.

### tenant_id Source of Truth

`tenant_id` is **always** derived from the verified JWT claims. It is **never** read
from the request body, query parameters, or any client-supplied field.

A single line that reads `tenant_id` from the request body is a one-line cross-tenant breach.

### Token Exchange Flow

```
Host page loads → loader.js reads data-widget-id
  → POST /api/widget/token  {widget_id: "..."}
       Origin: https://acme.com                    ← validated server-side
  ← 403 if origin not in DB allowed_origins
  ← 200 {token: "eyJ...", conversation_id: "uuid", expires_in: 1800}
  → iframe injected with token in URL params (not in DOM)
  → every chat: Authorization: Bearer eyJ...
  ← 401 if token missing / expired / tampered
```

### Guardrail Layers

Two layers — only one is tenant-editable:

1. **Platform rails** (mandatory, identical for all tenants):
   - Prompt injection detection
   - Jailbreak resistance
   - Cross-tenant refusal
   - PII redaction before logs/traces

   Tenants **cannot** weaken these. They fail CI when they regress.

2. **Tenant rails** (configurable per tenant in admin):
   - Allowed/blocked topics
   - Refusal tone
   - Agent persona
   - Enabled tools

### CI Gates

The following gates **block merge** on regression:
- `injection_redteam` — zero tolerance, all probes must be refused
- `redaction` — zero tolerance, no secret leaks in logs
- `classifier` — macro-F1 ≥ 0.75
- `agent_tool_selection` — ≥ 13/15
- `rag` — hit@5 ≥ 0.8, faithfulness ≥ 0.7
- `smoke-test` — docker-compose up must succeed

See `eval_thresholds.yaml` for committed thresholds.

### Right to Erasure

When a tenant is deleted, the following must be purged:
- `widgets`, `widget_sessions`, `tenant_config` rows (Postgres — cascades from `tenants`)
- pgvector embeddings scoped to `tenant_id`
- MinIO blobs under the tenant prefix
- Redis sessions: `widget_session:{conversation_id}` keys
- Audit logs are retained per compliance policy (not purged)

See Owner A's `DELETE /api/platform/tenants/{id}` endpoint for the erasure path.
