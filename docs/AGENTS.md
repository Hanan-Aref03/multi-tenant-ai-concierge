# AGENTS.md

## Project Focus

This repository is building a secure multi-tenant AI concierge SaaS. The priority is not a flashy chatbot; it is tenant isolation, safe routing, and a believable production architecture.

## Non-Negotiables

- Tenant isolation is the product promise.
- Always scope reads and writes by `tenant_id` and prefer defense in depth: RLS, repository filtering, token scoping, and memory isolation.
- Use a router-first, agent-second flow. Easy requests should not pay the agent cost.
- Keep platform guardrails immutable. Tenant-specific settings may change persona and policy, but they may not weaken cross-tenant or injection protection.
- Keep the serving stack lean. Do not move training frameworks into runtime containers.
- Preserve reproducibility with Docker Compose and GitHub Actions.

## Working Rules

- Read `docs/ARCHITECTURE_AND_WORKFLOW.md`, `docs/TEAM.md`, `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, and `.planning/ROADMAP.md` before changing implementation details.
- Put prompts in `prompts/`, evals in `evals/`, and tests in `tests/`.
- When in doubt, optimize for security, traceability, and demo reliability.
