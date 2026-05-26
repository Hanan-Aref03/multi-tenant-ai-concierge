# Data Model: Widget Auth, Admin UX & CI/CD (Owner D)

**Date**: 2026-05-25
**Feature**: specs/001-widget-auth-admin-cicd/spec.md

---

## Entities

### Widget

Represents one embeddable chat widget per tenant.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | PK, generated |
| `tenant_id` | UUID | FK → tenants.id, NOT NULL, RLS-enforced |
| `widget_id` | VARCHAR(64) | UNIQUE, public-facing identifier, URL-safe |
| `greeting` | TEXT | Default: "Hi! How can I help you?" |
| `accent_colour` | VARCHAR(7) | Hex colour, e.g. `#3B82F6`, validated format |
| `allowed_origins` | TEXT[] | Array of origin strings, e.g. `["https://acme.com"]` |
| `created_at` | TIMESTAMPTZ | Set on insert |
| `updated_at` | TIMESTAMPTZ | Set on update |

**RLS policy**: SELECT/INSERT/UPDATE/DELETE scoped to `current_setting('app.tenant_id')::uuid`.

**Validation rules**:
- `allowed_origins` entries must match `^https?://[a-z0-9.-]+(:\d+)?$`
- `accent_colour` must match `^#[0-9A-Fa-f]{6}$`
- `widget_id` is system-generated (UUID-derived slug), never admin-specified

---

### WidgetSession

Short-lived token record. The JWT is self-contained — this table is for audit and revocation only.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants.id |
| `widget_id` | UUID | FK → widgets.id |
| `conversation_id` | UUID | Generated per token exchange, links to Redis session |
| `origin` | TEXT | The validated origin from the token exchange request |
| `issued_at` | TIMESTAMPTZ | Set on insert |
| `expires_at` | TIMESTAMPTZ | issued_at + 30 min |
| `revoked` | BOOLEAN | Default FALSE — set TRUE on explicit revocation |

**Note**: Token validation is done in-memory via JWT signature + expiry. This table is not in the hot path. It exists for audit logs and for the right-to-erasure path (Owner A's purge job deletes rows by tenant_id).

**No RLS**: The token exchange endpoint runs as the service user and inserts with an explicit `tenant_id`. Reads are by `conversation_id` only.

---

### TenantConfig

Per-tenant agent and guardrail configuration. One row per tenant.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants.id, UNIQUE, RLS-enforced |
| `agent_persona` | TEXT | The system-prompt persona text |
| `enabled_tools` | TEXT[] | Subset of `["rag_search","capture_lead","escalate"]` |
| `allowed_topics` | TEXT[] | Guardrail allow-list topics |
| `blocked_topics` | TEXT[] | Guardrail block-list topics |
| `refusal_tone` | VARCHAR(32) | One of: `polite`, `firm`, `brief` |
| `updated_at` | TIMESTAMPTZ | Set on update |

**RLS policy**: SELECT/UPDATE scoped to `current_setting('app.tenant_id')::uuid`.

**Validation rules**:
- `enabled_tools` entries must be in the allowed set
- `refusal_tone` must be one of the three named values

---

### Lead

Visitor leads captured by the agent. Owned by Owner B (agent slice) but read by Owner D's admin leads view.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants.id, RLS-enforced |
| `visitor_name` | TEXT | May be null if not provided |
| `contact` | TEXT | Email or phone, redacted in logs |
| `intent` | TEXT | Classifier-assigned intent label |
| `conversation_id` | UUID | Links to the Redis session (for context) |
| `captured_at` | TIMESTAMPTZ | Set on insert |

**RLS policy**: SELECT scoped to `current_setting('app.tenant_id')::uuid`. Admin UI gets read-only access.

---

## Redis Session Schema

Session data stored by the agent (Owner B) but scoped per conversation-id set by Owner D's token exchange.

```
Key:   widget_session:{conversation_id}
Value: JSON { "tenant_id": "...", "widget_id": "...", "messages": [...] }
TTL:   1800 seconds (30 minutes, matches JWT expiry)
```

The `conversation_id` is embedded in the JWT so the chat endpoint can look up the session without a DB call.

---

## CI Configuration Schema (`eval_thresholds.yaml`)

```yaml
# eval_thresholds.yaml — committed thresholds for CI gates
# All gates read this file. A missing gate key causes the pipeline to fail.

classifier:
  metric: macro_f1
  threshold: 0.75
  comparison: ">="

agent_tool_selection:
  metric: pass_count
  total: 15
  threshold: 13
  comparison: ">="

rag:
  hit_at_5:
    threshold: 0.8
    comparison: ">="
  faithfulness:
    threshold: 0.7
    comparison: ">="

injection_redteam:
  metric: refused_count
  total: 10        # number of probes
  threshold: 10    # all must be refused
  comparison: "=="

redaction:
  metric: leaked_count
  threshold: 0
  comparison: "=="
```

---

## State Transitions

### Widget Session Lifecycle

```
[Token Exchange Request]
  → validate origin (DB lookup + Redis cache)
  → issue JWT (tenant_id, widget_id, conversation_id, exp)
  → insert WidgetSession row
  → set Redis session key
        ↓
[Chat Messages] — verify JWT on each request
        ↓
[Session Expiry / TTL] → Redis key deleted, JWT rejected
        ↓
[Optional: Explicit Revocation] → revoked=TRUE in WidgetSession
```

### Admin Config Update Lifecycle

```
[Admin saves form]
  → PUT /api/admin/widget or /api/admin/config
  → FastAPI validates JWT role=tenant_admin
  → RLS scopes write to this tenant
  → DB updated
  → Redis CORS cache invalidated (DEL widget_origins:{tenant_id})
  → Response 200 → Streamlit shows success toast
```
