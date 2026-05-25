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
- `apps/api/`
- `services/rag/`
- `services/router/`
- `services/agent/`
- `packages/contracts/`

First moves:
1. Define the FastAPI backend boundaries.
2. Wire tenant-scoped retrieval and the router-first flow.
3. Keep the agent bounded to the three allowed tools.

## Owner B - Mohammad

Primary responsibility:
- `infrastructure/postgres/`
- `infrastructure/vault/`
- tenant auth and RLS logic inside the API

First moves:
1. Create the tenant data model.
2. Implement role-based access and request-scoped tenant context.
3. Make cross-tenant access fail at the database layer.

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
