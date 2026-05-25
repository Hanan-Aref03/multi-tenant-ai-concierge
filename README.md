# multi-tenant-ai-concierge

Secure multi-tenant AI SaaS for business websites.

The big rule is simple: Tenant A must never see Tenant B data.

## Team Ownership

| Member | Primary Areas | First Things To Build |
|--------|---------------|-----------------------|
| Hanan | `apps/api/`, `services/rag/`, `services/router/`, `services/agent/`, `packages/contracts/` | Backend architecture, tenant-safe API contracts, retrieval pipeline, router/agent split |
| Mohammad | `infrastructure/postgres/`, `infrastructure/vault/`, `services/security/` concepts inside API | Auth, RLS, tenant provisioning, audit logging, secrets, rate limits |
| Rayan | `apps/modelserver/`, `services/guardrails/`, `evals/`, `tests/security/` | Classifier, guardrails, red-team evals, redaction, model-serving checks |
| Ali Faddel | `apps/widget/`, `apps/admin/`, `.github/workflows/`, `scripts/` | Widget UI, admin dashboard, CI/CD, bootstrap scripts, release automation |

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
3. Build from the API spine outward.
4. Protect tenant isolation at every layer.

