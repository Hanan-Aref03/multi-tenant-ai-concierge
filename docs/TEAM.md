# Team Ownership

This document turns the project split into a working repo map.

## Owner Map

| Owner | Team Member |
|-------|-------------|
| Owner A | Hanan |
| Owner B | Mohammad |
| Owner C | Rayan |
| Owner D | Ali Faddel |

## Owner A - Hanan

Primary responsibility:
- `infrastructure/postgres/`
- `infrastructure/vault/`
- `infrastructure/redis/`
- `infrastructure/minio/`
- `apps/api/app/core/`
- `apps/api/app/db/`
- `apps/api/app/api/v1/tenants.py`
- `scripts/verify_isolation.ps1`
- Execution plan: [docs/HANAN_PLATFORM_SPINE_PLAN.md](HANAN_PLATFORM_SPINE_PLAN.md)

First moves:
1. Create the tenant data model and the per-request tenant context.
2. Implement auth, RLS, provisioning, erasure, and audit logging.
3. Make cross-tenant access fail at the database layer.

## Owner B - Mohammad

Primary responsibility:
- `services/router/`
- `services/rag/`
- `services/agent/`
- `services/embeddings/`
- `prompts/`
- `evals/rag/`
- `evals/agent/`

First moves:
1. Stand up the router-first flow and the bounded agent loop.
2. Wire tenant-filtered retrieval and Redis short-term memory.
3. Build the golden sets for tool selection and retrieval quality.

## Owner C - Rayan

Primary responsibility:
- `apps/modelserver/`
- `services/guardrails/`
- `evals/`
- `tests/security/`

First moves:
1. Train and export the classifier artifact.
2. Define platform guardrails and redaction rules.
3. Build eval gates that can block regressions.

## Owner D - Ali Faddel

Primary responsibility:
- `apps/widget/`
- `apps/admin/`
- `.github/workflows/`
- `scripts/`

First moves:
1. Build the widget shell and embed flow.
2. Build the admin dashboard for tenant operators.
3. Set up CI so every push proves the repo still works.

## Shared Rule

Everyone reviews the tenant isolation path before merging anything.
