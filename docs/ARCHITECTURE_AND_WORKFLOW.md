# Architecture and Workflow

This repository is a modular monorepo for a secure multi-tenant AI concierge.
The product goal is not just chat. The goal is tenant isolation by default.

## Canonical Folder Model

- `apps/` - deployable app slices and runtime entrypoints
- `backend/` - legacy API/runtime host still used by the current compose flow
- `admin/` - Streamlit admin runtime
- `widget/` - standalone widget runtime and build
- `services/` - shared domain logic for routing, RAG, agent, guardrails, and embeddings
- `infrastructure/` - database migrations, Redis/Vault/MinIO notes, and Docker guidance
- `prompts/` - system, router, agent, and guardrail prompts
- `evals/` - classifier, RAG, agent, red-team, and release gates
- `tests/` - unit, integration, and security verification
- `scripts/` - bootstrap, verification, and team checks
- `docs/` - stable human-readable docs
- `.planning/` - living project state, roadmap, and requirements
- `.github/workflows/` - CI, eval, and release automation

## Team Split

- Owner A / Hanan: platform spine, tenancy, RLS, provisioning, auth, audit
- Owner B / Mohammad: router, RAG, agent, memory, prompts, retrieval evals
- Owner C / Rayan: model server, guardrails, red-team, redaction, security evals
- Owner D / Ali Faddel: widget, admin, CI/CD, scripts, release automation

See [docs/TEAM.md](TEAM.md) for the detailed owner map.

## Working Rules

- Branch from `dev`
- Use `<owner>/<type>-<short-description>` branch names
- Never work directly on `main`
- Merge feature branches into `dev`
- Merge `dev` into `main` only for release
- Run the relevant tests before commit
- Run `powershell -ExecutionPolicy Bypass -File scripts/run_team_checks.ps1` before pushing cross-team changes

## Security Rules

- `tenant_id` must flow through every data path
- Enforce tenant isolation in the database, repository, widget token, and memory layers
- Use short-lived signed widget tokens and server-side origin validation
- Treat CORS as a convenience, not security
- Keep the agent bounded: router first, agent second
- Keep runtime containers lean; do not ship training frameworks in production images

## Shared Contracts

- Widget token exchange is tenant-scoped and origin-checked
- Admin actions are audit-logged
- CI must gate lint, tests, evals, and smoke checks
- The release branch should only move when the repo is green

## Retired Scaffolding

The old SpecKit workspace was removed to keep the repo simple:

- `specs/`
- `.claude/`
- `.specify/`

The useful guidance from those folders now lives in this doc, `docs/`, and `.planning/`.

## Where To Start

- [docs/TEAM.md](TEAM.md)
- [docs/REPO_STRUCTURE.md](REPO_STRUCTURE.md)
- [docs/BRANCHING.md](BRANCHING.md)
- [docs/BRANCH_PROTECTION.md](BRANCH_PROTECTION.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [.planning/PROJECT.md](../.planning/PROJECT.md)
- [.planning/ROADMAP.md](../.planning/ROADMAP.md)
- [docs/HANAN_PLATFORM_SPINE_PLAN.md](HANAN_PLATFORM_SPINE_PLAN.md) if you are Hanan
