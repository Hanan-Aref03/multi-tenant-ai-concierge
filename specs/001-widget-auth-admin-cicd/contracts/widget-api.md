# API Contracts: Widget Auth & Admin (Owner D)

**Date**: 2026-05-25
**Base URL**: `http://localhost:8000` (dev) | `https://api.concierge.example.com` (prod)

---

## Widget Token Exchange

### `POST /api/widget/token`

Exchanges a public `widget_id` + origin for a short-lived signed session token.

**Auth**: None (public endpoint)

**Request**:
```json
{
  "widget_id": "acme-corp-widget-1a2b3c"
}
```

**Headers required**:
- `Origin: https://acme.com` — validated server-side against `allowed_origins`

**Responses**:

| Status | Condition | Body |
|--------|-----------|------|
| 200 | Origin allowed, widget active | `{ "token": "<JWT>", "conversation_id": "<uuid>", "expires_in": 1800 }` |
| 403 | Origin not in `allowed_origins` | `{ "detail": "Origin not permitted" }` |
| 404 | `widget_id` not found | `{ "detail": "Widget not found" }` |
| 422 | Malformed request body | Standard FastAPI validation error |

**JWT Claims**:
```json
{
  "tenant_id": "uuid",
  "widget_id": "uuid",
  "conversation_id": "uuid",
  "origin": "https://acme.com",
  "exp": 1748000000,
  "iat": 1747998200
}
```

**Security notes**:
- `tenant_id` is set from DB lookup, never from request body
- `Origin` header absence → 403 (treat as disallowed)
- Empty `allowed_origins` list → 403 always

---

## Widget Config (Theme)

### `GET /api/widget/{widget_id}/config`

Returns public widget theme and greeting. No auth required (public, cached heavily).

**Response** `200`:
```json
{
  "greeting": "Hi! How can we help you today?",
  "accent_colour": "#3B82F6"
}
```

**Response** `404`: widget not found.

---

## Chat Endpoint

### `POST /api/chat`

Sends a visitor message to the agent. `tenant_id` is extracted exclusively from the token.

**Auth**: `Authorization: Bearer <widget-session-JWT>`

**Request**:
```json
{
  "conversation_id": "uuid",
  "message": "What are your business hours?"
}
```

**Responses**:

| Status | Condition | Body |
|--------|-----------|------|
| 200 | Success | `{ "reply": "...", "conversation_id": "uuid" }` |
| 401 | Missing, expired, or invalid token | `{ "detail": "Token invalid or expired" }` |
| 429 | Rate limit exceeded for this widget session | `{ "detail": "Rate limit exceeded" }` |

**Security notes**:
- Any `tenant_id` field in the request body is ignored
- Token is verified (signature + expiry) by middleware before the handler runs

---

## Admin — Widget Settings

### `GET /api/admin/widget`

Returns the authenticated tenant's widget config.

**Auth**: `Authorization: Bearer <tenant-admin-JWT>`

**Response** `200`:
```json
{
  "widget_id": "acme-corp-widget-1a2b3c",
  "greeting": "Hi! How can we help?",
  "accent_colour": "#3B82F6",
  "allowed_origins": ["https://acme.com", "https://acme.co.uk"],
  "embed_snippet": "<script src=\"/widget.js\" data-widget-id=\"acme-corp-widget-1a2b3c\"></script>"
}
```

**Response** `403`: Caller is not a `tenant_admin`.

---

### `PUT /api/admin/widget`

Updates widget settings for the authenticated tenant.

**Auth**: `Authorization: Bearer <tenant-admin-JWT>`

**Request**:
```json
{
  "greeting": "Welcome! How can we help?",
  "accent_colour": "#6366F1",
  "allowed_origins": ["https://acme.com"]
}
```

**Responses**:

| Status | Condition |
|--------|-----------|
| 200 | Updated successfully |
| 403 | Not a tenant_admin |
| 422 | Invalid origin format or colour |

**Side effect**: Invalidates Redis CORS cache for this tenant.

---

## Admin — Agent & Guardrail Config

### `GET /api/admin/config`

Returns agent persona and guardrail settings for the tenant.

**Auth**: `Authorization: Bearer <tenant-admin-JWT>`

**Response** `200`:
```json
{
  "agent_persona": "You are a helpful assistant for Acme Corp...",
  "enabled_tools": ["rag_search", "capture_lead"],
  "allowed_topics": ["product info", "pricing"],
  "blocked_topics": ["competitors"],
  "refusal_tone": "polite"
}
```

---

### `PUT /api/admin/config`

Updates agent and guardrail config.

**Auth**: `Authorization: Bearer <tenant-admin-JWT>`

**Request**:
```json
{
  "agent_persona": "...",
  "enabled_tools": ["rag_search", "capture_lead", "escalate"],
  "allowed_topics": ["product info"],
  "blocked_topics": ["competitors", "pricing"],
  "refusal_tone": "firm"
}
```

**Validation**:
- `enabled_tools` — only values in `["rag_search", "capture_lead", "escalate"]` accepted
- `refusal_tone` — only `"polite"`, `"firm"`, `"brief"` accepted

---

## Admin — Leads

### `GET /api/admin/leads`

Returns captured leads for the authenticated tenant.

**Auth**: `Authorization: Bearer <tenant-admin-JWT>`

**Query params**: `?limit=50&offset=0`

**Response** `200`:
```json
{
  "total": 142,
  "leads": [
    {
      "id": "uuid",
      "visitor_name": "Jane Smith",
      "contact": "jane@example.com",
      "intent": "sales",
      "captured_at": "2026-05-25T10:30:00Z"
    }
  ]
}
```

**Security**: RLS policy ensures only this tenant's leads are returned regardless of query.

---

## Loader Script Contract

### `GET /widget.js`

Public JavaScript loader. No auth required. Heavily cached (1 week).

**Behaviour**:
1. Reads `data-widget-id` from the `<script>` element
2. POSTs to `/api/widget/token` with the current `window.location.origin`
3. On success: creates an `<iframe>` pointing to `/widget/embed/{conversation_id}?token={token}`
4. On failure: logs error silently, does not break host page

**Response headers**:
- `Content-Type: application/javascript`
- `Cache-Control: public, max-age=604800, immutable`
