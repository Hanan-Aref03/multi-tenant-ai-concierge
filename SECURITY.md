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
   - Prompt/system disclosure refusal
   - PII redaction before logs/traces

   Tenants **cannot** weaken these. NeMo Guardrails is loaded as the programmable rail layer, while deterministic Python rules remain as defense-in-depth. They fail CI when they regress.

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

---

## Guardrails Architecture (Owner C / Rayan)

### Platform Rails (Immutable)

Implemented as a hybrid layer:
- NeMo config: `services/guardrails/nemo/config.yml` and `services/guardrails/nemo/rails.co`
- NeMo adapter: `services/guardrails/nemo_adapter.py`
- Deterministic fallback rules: `services/guardrails/rules.py`

The sidecar loads NeMo through `RailsConfig` and `LLMRails` when `GUARDRAILS_USE_NEMO=true` and falls back to deterministic rules if NeMo is unavailable. Set `GUARDRAILS_NEMO_STRICT=true` to fail closed when NeMo cannot load. Platform rails are evaluated on every inbound message before routing/model work and **cannot** be overridden by tenant configuration.

| Rule | Layer | Decision on match |
|------|-------------|------------------|
| Prompt disclosure | NeMo + regex fallback | `blocked_prompt_disclosure` |
| Cross-tenant access | NeMo + regex fallback | `blocked_cross_tenant` |
| Prompt injection | NeMo + regex fallback | `blocked_prompt_injection` |
| Jailbreak | NeMo + regex fallback | `blocked_jailbreak` |
| Tenant blocked topic | Tenant policy, stricter only | `blocked_tenant_topic` |

A blocked sidecar check returns the existing response schema with `allowed=false`, a `decision` field, and a redacted message. The chat API turns blocked messages into a safe refusal.

### Tenant Rails (Configurable)

Tenant admins configure these in the admin dashboard. They can restrict or customize behaviour but **cannot disable platform rails**:
- Allowed/blocked topics
- Refusal tone and persona
- Which tools the agent may call

Currently, the sidecar minimally enforces `blocked_topics` when a `tenant_policy` is supplied. Persona, refusal tone, allowed topics, and enabled tools are stored/admin-editable but are not full NeMo tenant rails yet.

### Guardrails Service Contract

The guardrails service runs as a separate container (port 8011). All inbound API calls must pass through it. Direct calls that bypass the guardrails endpoint are a security violation.

```
POST /v1/check
  Request:  { tenant_id, message, tenant_policy? }
  Response: { allowed, decision, reason, redacted_message }
```

The `redacted_message` field is the input with PII stripped. Use this — not the raw input — for logging, memory, and downstream LLM calls.

---

## Redaction (Owner C / Rayan)

Implemented in `services/guardrails/redaction.py`. This is custom regex-based redaction, not NeMo/Presidio redaction. Runs on every message **before** it is written to logs, audit records, Redis session memory, or LLM context.

### Patterns Redacted

| Type | Pattern |
|------|---------|
| Authorization tokens | `Authorization: Bearer ...` |
| OpenAI API keys | `sk-...` |
| Google service keys | `gsk_...` |
| Slack tokens | `xoxb-...` |
| GitHub tokens | `ghp_...` |
| Email addresses | RFC 5321 regex |
| Phone numbers | E.164 and common formats |

Redacted values are replaced with `[REDACTED]` in the output. The `RedactionResult` object carries a tuple of what was redacted, for audit purposes, but the redacted values themselves are never logged.

### CI Verification

The `redaction` eval gate sends a synthetic API key (`sk-test-deadbeef…`) through the chat flow and then scans log files and Docker Compose logs for the unredacted pattern. **Zero tolerance** — any leak blocks merge.

```
evals/redaction.py --thresholds eval_thresholds.yaml --stub
```

---

## Artifact Integrity (Owner C / Rayan)

The model server verifies the SHA-256 of the classifier artifact against `model_card.json` on every startup. If the hash does not match, the server refuses to start and returns 503 on all inference requests. This prevents:
- Corrupted artifact from silent mis-classification
- Tampered artifact from a supply-chain attack on the model file

The `model_checksum_valid` field in `GET /health` is monitored in the smoke test and must be `true` before the API is allowed to serve traffic (via `depends_on: modelserver: condition: service_healthy`).
