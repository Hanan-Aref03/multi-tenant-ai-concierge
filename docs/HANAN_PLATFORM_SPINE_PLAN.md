# Hanan Platform Spine Plan

Owner: Hanan
Role: Owner A
Branch: `hanan/feat-platform-spine`
Status: implemented and verified

## Mission

Build the secure platform spine for Concierge: tenant provisioning, auth, RLS, audit logging, and a reproducible local stack. This branch is the foundation for every other slice, so the first priority is always tenant isolation.

## Hanan Guardrails

- Do not widen scope into RAG, widget UX, model serving, or guardrails work.
- Keep every read and write scoped by `tenant_id`.
- Treat database enforcement as the real wall, not just application filters.
- Verify before pushing: lint, tests, and any isolation checks relevant to the files changed.
- Stay on `hanan/feat-platform-spine` until this slice is ready for review.

## Step 1: Confirm the platform contract

Goal:
- Re-read the project plan and make sure this branch only covers the platform spine.

Files to use:
- `.planning/PROJECT.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `docs/TEAM.md`

Done when:
- The branch scope is clear.
- The Hanan-owned files for this phase are identified.

## Step 2: Define the tenant data model

Goal:
- Create the base tenant schema and the fields needed for isolation, provisioning, and auditability.

Files to build:
- `infrastructure/postgres/migrations/0001_init.sql`
- `apps/api/app/db/models/tenant.py`
- `apps/api/app/db/models/conversation.py`
- `apps/api/app/db/models/content.py`
- `apps/api/app/db/models/lead.py`

Done when:
- The tenant model is explicit.
- The schema has the fields needed for `tenant_id` isolation.
- The repo documents how the platform stores tenant state.

## Step 3: Add request-scoped tenant context

Goal:
- Make every request carry the active tenant identity through the API, DB session, and service layer.

Files to build:
- `apps/api/app/core/tenant_context.py`
- `apps/api/app/db/session.py`
- `apps/api/app/core/security.py`
- `apps/api/app/main.py`

Done when:
- A request can resolve a tenant safely.
- The tenant context is available to DB and service helpers.
- The code path is ready for RLS enforcement.

## Step 4: Implement auth and platform access

Goal:
- Add the platform-facing auth and role boundaries for tenant manager, tenant admin, and member roles.

Files to build:
- `apps/api/app/api/v1/tenants.py`
- `apps/api/app/api/router.py`
- `apps/api/app/core/security.py`
- `apps/api/app/api/v1/health.py`

Done when:
- The platform can distinguish privileged tenant actions from normal tenant actions.
- Cross-tenant access is blocked at the application boundary.
- The API structure is ready for later feature work.

## Step 5: Enforce RLS and isolation at the database layer

Goal:
- Turn tenant isolation into a database rule, not just an API convention.

Files to build:
- `infrastructure/postgres/migrations/0002_rls.sql`
- `scripts/verify_isolation.ps1`
- `tests/security/test_tenant_isolation.py`

Done when:
- RLS policies exist for tenant-scoped tables.
- Request-scoped session variables are defined.
- Cross-tenant reads and writes fail in tests.

## Step 6: Wire provisioning, erasure, and audit logging

Goal:
- Support the lifecycle actions the platform owner needs: create tenant, invite first admin, suspend, erase, and audit the action trail.

Files to build:
- `apps/api/app/services/audit_service.py`
- `apps/api/app/api/v1/tenants.py`
- `infrastructure/minio/buckets.md`
- `infrastructure/vault/policies/tenant.hcl`

Done when:
- Tenant lifecycle actions are documented and traceable.
- Audit events are written for sensitive changes.
- The storage and secrets story is clear in the repo docs.

## Step 7: Make the local stack reproducible

Goal:
- Ensure the platform can be started the same way by every teammate.

Files to build:
- `docker-compose.yml`
- `infrastructure/docker/README.md`
- `.env.example`
- `Makefile`

Done when:
- The service layout is documented.
- Environment values are clearly listed.
- The local stack expectations are obvious from the repo.

## Step 8: Verify and document

Goal:
- Make the branch easy for the next person to review and continue.

Files to update:
- `docs/TEAM.md`
- `docs/REPO_STRUCTURE.md`
- `README.md`
- `.planning/STATE.md`

Done when:
- The Hanan plan is discoverable from the team docs.
- The project state reflects that this branch is the Hanan platform spine branch.
- The branch can be reviewed without guessing what Hanan owns.

## Hanan Delivery Checklist

- [x] Tenant schema is defined
- [x] Request tenant context is wired
- [x] Auth and role boundaries exist
- [x] RLS policies are in place
- [x] Provisioning and audit logging are documented
- [x] Local stack is reproducible
- [x] Isolation checks are written
- [x] Docs point clearly to the Hanan branch

## Validation

- `python -m unittest discover -s tests -t . -p "test_*.py"` passes
- `powershell -ExecutionPolicy Bypass -File scripts/verify_isolation.ps1` passes
- `python -m compileall apps services tests` passes

## Hanan File Map

Most likely files for this branch:

- `apps/api/app/main.py`
- `apps/api/app/core/config.py`
- `apps/api/app/core/security.py`
- `apps/api/app/core/tenant_context.py`
- `apps/api/app/api/router.py`
- `apps/api/app/api/v1/tenants.py`
- `apps/api/app/db/session.py`
- `apps/api/app/db/models/tenant.py`
- `infrastructure/postgres/migrations/0001_init.sql`
- `infrastructure/postgres/migrations/0002_rls.sql`
- `tests/security/test_tenant_isolation.py`
- `scripts/verify_isolation.ps1`

## Hanan Definition of Done

This branch is done when:

1. The platform spine is clearly documented.
2. Tenant isolation is enforced by design and verified by tests.
3. The repo can be used by the next teammate without ambiguity.
