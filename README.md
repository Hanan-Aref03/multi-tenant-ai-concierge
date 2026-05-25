# multi-tenant-ai-concierge

Secure multi-tenant AI SaaS for business websites.

The big rule is simple: Tenant A must never see Tenant B data.

## Team Ownership

| Owner | Member | Primary Areas | First Things To Build |
|-------|--------|---------------|-----------------------|
| Owner A | Hanan | `infrastructure/postgres/`, `infrastructure/vault/`, `infrastructure/redis/`, `infrastructure/minio/`, `apps/api/app/core/`, `apps/api/app/db/` | Platform, tenancy, isolation, provisioning, auth, RLS, audit logging |
| Owner B | Mohammad | `services/router/`, `services/rag/`, `services/agent/`, `services/embeddings/`, `prompts/`, `evals/rag/`, `evals/agent/` | Agent, RAG, memory, routing, tool contracts, retrieval quality |
| Owner C | Rayan | `apps/modelserver/`, `services/guardrails/`, `evals/classifier/`, `evals/redteam/`, `tests/security/` | Classifier, guardrails, red-team evals, redaction, model-serving checks |
| Owner D | Ali Faddel | `apps/widget/`, `apps/admin/`, `.github/workflows/`, `scripts/` | Widget UI, admin dashboard, CI/CD, bootstrap scripts, release automation |

## Repository Shape

- `apps/` - deployable apps the team runs or demos
- `services/` - shared domain logic used by the apps
- `infrastructure/` - local stack, database, secrets, and runtime plumbing
- `packages/` - shared contracts and cross-app interfaces
- `prompts/` - system prompts, routing prompts, and guardrail prompts
- `evals/` - offline tests, red-team cases, and release checks
- `tests/` - automated verification and security tests
- `docs/` - architecture, team ownership, and repo structure notes
- `.planning/` - project planning artifacts from GSD

## Start Here

1. Read `.planning/PROJECT.md` to keep the core value in view.
2. Read `docs/TEAM.md` to see who owns what.
3. Read `docs/BRANCHING.md` before starting work.
4. Read `docs/BRANCH_PROTECTION.md` before touching GitHub settings.
5. Read `CONTRIBUTING.md` before committing or pushing.
6. Build from the API spine outward.
7. Protect tenant isolation at every layer.
