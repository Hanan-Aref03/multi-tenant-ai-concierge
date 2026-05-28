# DESIGN.md — Concierge Platform Architecture

Owner A (Hanan) is primary author of this document.

## System Overview

Concierge is a multi-tenant AI SaaS where each tenant gets an isolated knowledge base, widget, and assistant. The fundamental constraint is: **Tenant A must never read or write Tenant B's data, even if application-layer code forgets a filter.**

```
                         ┌─────────────────────────────────────────────────┐
                         │  Tenant's public website (acme.com)             │
                         │                                                  │
                         │  <script src="…/loader.js"                      │
                         │          data-widget-id="wgt_abc123"></script>   │
                         └───────────────────┬─────────────────────────────┘
                                             │
                              POST /api/widget/token
                              (Origin validated server-side)
                                             │
                         ┌───────────────────▼─────────────────────────────┐
                         │                  API (FastAPI)                  │
                         │                                                  │
                         │  ┌─────────────┐  ┌──────────┐  ┌───────────┐  │
                         │  │  Widget Auth│  │  Router  │  │  Admin    │  │
                         │  │  (JWT)      │  │  (LLM+   │  │  (RBAC)   │  │
                         │  └─────────────┘  │  Classif)│  └───────────┘  │
                         │                   └────┬─────┘                  │
                         └────────────────────────┼────────────────────────┘
                                                  │
               ┌──────────────┬──────────────────┼─────────────────┐
               │              │                  │                  │
         ┌─────▼─────┐  ┌─────▼─────┐   ┌───────▼───────┐  ┌──────▼──────┐
         │ Modelserver│  │  RAG      │   │  Agent        │  │ Guardrails  │
         │ (Port 8010)│  │  (pgvec)  │   │  (tools)      │  │ (Port 8011) │
         └─────┬──────┘  └─────┬─────┘   └───────┬───────┘  └──────┬──────┘
               │               │                  │                  │
         ┌─────▼───────────────▼──────────────────▼──────────────────▼──────┐
         │                     Data Layer                                    │
         │  PostgreSQL (RLS)  │  Redis (sessions + embedding cache)          │
         │  pgvector          │  MinIO (tenant blobs)  │  Vault (secrets)    │
         └───────────────────────────────────────────────────────────────────┘
```

---

## Tenant Isolation — Defense in Depth

Isolation is enforced at four independent layers. Breaking through one layer does not break the others.

### Layer 1 — Database (PostgreSQL RLS)

Every tenant-scoped table has a Row-Level Security policy that reads the current `tenant_id` from a session variable set at connection time:

```sql
ALTER TABLE widget_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON widget_sessions
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

A query that omits `SET LOCAL app.tenant_id = '...'` returns zero rows. This is the last line of defense — it works even if every application layer above it is bypassed.

### Layer 2 — Repository Scoping

Every service function that touches tenant data accepts `tenant_id` as a required parameter and includes it in every query predicate. There is no code path that reads tenant data without an explicit scope argument.

### Layer 3 — Signed Widget Token (JWT)

`tenant_id` is embedded in a short-lived JWT signed with a per-widget secret. It is extracted from the verified token claims on every request. It is **never** read from the request body, query params, or any client-supplied field.

```
# Safe: tenant_id from verified JWT
tenant_id = token_claims["tenant_id"]

# Unsafe: never do this
tenant_id = request.body.get("tenant_id")  # one-line cross-tenant breach
```

### Layer 4 — Session Memory (Redis)

Widget session keys are namespaced by `widget_session:{conversation_id}`, where `conversation_id` is derived from the signed token. A visitor cannot guess or craft a `conversation_id` that belongs to another tenant.

---

## Scaling Story

### Stateless API Tier

The API service is stateless: no local files, no in-process session storage. Horizontal scaling is a matter of adding replicas behind a load balancer. The only shared state is in PostgreSQL and Redis, both of which are connection-pooled via SQLAlchemy async + asyncpg.

### Database Scaling Path

| Stage | Approach | When |
|-------|----------|------|
| Demo | Single Postgres 16 on Docker | ≤ 10 tenants |
| Growth | Read replicas for SELECT-heavy paths (retrieval, admin reads) | 10–500 tenants |
| Scale | Citus sharding on `tenant_id` | 500+ tenants |
| PGvector | pgvector on the same instance; at scale, Weaviate or Qdrant with tenant namespaces | 100M+ vectors |

RLS policies carry forward to Citus sharding because the shard key (`tenant_id`) matches the isolation key.

### Embedding Cache

`sentence-transformers/all-MiniLM-L6-v2` runs as an async CPU process. Embeddings are cached in Redis with a 24-hour TTL keyed by `emb:{tenant_id}:{sha256[:16]}`. Cache hit rate is high for FAQ-style content (repeated queries). This keeps the CPU-bound embedding path off the hot request path for returning visitors.

### Content Ingestion (Background)

Content uploads are chunked (2000-char chunks, 250-char overlap) and indexed asynchronously. The embedding + pgvector insert runs in the background so the admin upload endpoint returns immediately. This decouples ingestion throughput from API latency.

### Rate Limiting

Redis-backed sliding window counter per widget token, enforced in the API middleware before any LLM call. Per-tenant limits are configurable in the admin panel. This prevents any single tenant from exhausting the shared modelserver or guardrails capacity.

### Model Server (Port 8010)

The classifier runs as a stateless sidecar. It loads a 3.2 MB joblib artifact at startup, verifies its SHA-256, and serves inference at 0.32ms/request. It can be scaled horizontally and behind a simple round-robin balancer — each instance is identical and reads the same artifact from a shared volume or object store.

---

## Data Flow — Widget Chat Turn

```
1. Visitor types message in widget iframe
2. Widget POSTs to /api/chat with Authorization: Bearer <token>
3. WidgetAuthMiddleware validates JWT → extracts tenant_id, widget_id
4. Guardrails sidecar checks for injection/jailbreak → block or pass
5. Router classifies intent (calls modelserver, falls back to LLM)
6. Route decision:
   a. faq / knowledge_search → RAG: embed query → pgvector search → LLM answer
   b. greeting / off_topic   → direct canned reply (no LLM)
   c. sales_or_leads         → agent: capture_lead tool
   d. human_request          → agent: escalate tool
   e. low confidence         → agent: multi-turn tool-calling
7. Response + audit log written to Postgres
8. Reply streamed to widget
```

---

## Content Ingestion — Admin Upload

```
Admin uploads PDF/TXT/FAQ
  → chunked (recursive splitter, FAQ-aware)
  → embedded (MiniLM on CPU, Redis-cached)
  → pgvector INSERT with tenant_id
  → content row marked indexed
```

Updating content: delete old chunks by `content_id`, re-index. Stale answers cannot persist.

---

## Erasure (Right to Erasure)

Tenant deletion cascades through all storage layers:

| Layer | Mechanism |
|-------|-----------|
| Postgres | `DELETE FROM tenants WHERE id = $1` cascades to all child tables via FK |
| pgvector | `DELETE FROM embeddings WHERE tenant_id = $1` |
| Redis | `DEL widget_session:{conversation_id}` for all sessions in the tenant |
| MinIO | `mc rm --recursive s3/tenant-uploads/{tenant_id}/` |
| Audit logs | Retained per compliance policy — not deleted |

---

## Local Development Stack

`docker compose up` starts the full stack:

| Service | Port | Role |
|---------|------|------|
| postgres | 5432 | Data + pgvector |
| redis | 6379 | Session + embedding cache |
| minio | 9000/9001 | Object storage (console at 9001) |
| vault | 8200 | Secrets (dev mode, token = `change-me`) |
| modelserver | 8010 | Classifier sidecar |
| guardrails | 8011 | Guardrails sidecar |
| api | 8000 | FastAPI backend |
| admin | 8501 | Streamlit admin dashboard |
| widget | 3000 | React widget (nginx) |

See `RUNBOOK.md` for startup, health-check, and teardown commands.
