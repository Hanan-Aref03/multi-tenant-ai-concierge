# multi-tenant-ai-concierge

## What This Is

A secure multi-tenant AI SaaS platform where businesses sign up, manage their own CMS content, and embed an AI assistant on their public site. Each tenant gets isolated data, embeddings, widget configuration, conversations, and operational logs. The assistant answers from tenant-owned content, captures leads, and escalates to humans when it cannot help.

## Core Value

Tenant A must never be able to access Tenant B data, even if a developer forgets a filter or a prompt becomes adversarial.

## Requirements

### Validated

(None yet - ship to validate)

### Active

- [ ] Tenant provisioning, auth, and role-based access work per tenant.
- [ ] Tenant content can be uploaded, chunked, and retrieved with tenant-scoped knowledge search.
- [ ] A public widget can be embedded safely and can chat with the tenant's assistant.
- [ ] The assistant can route easy questions directly and use tool-calling for hard questions.
- [ ] Cross-tenant access is blocked at the database, repository, widget-token, and memory layers.
- [ ] Guardrails, audit logs, and eval gates keep the platform safe and demo-ready.

### Out of Scope

- Native mobile apps - the assignment is web-first with an embeddable widget and admin dashboard.
- Fine-tuning large foundation models in production - the brief calls for lean serving plus hosted APIs.
- Multi-region active-active infrastructure - unnecessary for the class demo and too much operational overhead.
- Voice or multimodal assistant channels - not required for the demo and would add unrelated surface area.
- Full CRM or ticketing product - lead capture and escalation are enough for v1.

## Context

- Shared repo for a team of four: Hanan (architecture + AI integration), Mohammad (backend + security), Rayan (ML + guardrails), and Ali Faddel (frontend + widget + CI/CD).
- Brief owner mapping: Owner A = Hanan, Owner B = Mohammad, Owner C = Rayan, Owner D = Ali Faddel.
- The project brief explicitly centers tenant isolation: RLS, tenant-scoped pgvector, signed widget tokens, per-tenant origin checks, audit logs, and PII redaction.
- Recommended stack from the brief: FastAPI, React + Vite widget, Streamlit admin, PostgreSQL, pgvector, Redis, MinIO, Vault, OpenAI APIs, NeMo Guardrails, GitHub Actions, and Docker Compose.
- Deadline pressure is high: the brief is structured around a five-day build and Friday demo, so the plan should prioritize end-to-end slices over perfect layering.
- The assistant should use a workflow-router first and a bounded tool-calling agent only for hard turns.

## Constraints

- **Security**: Tenant isolation must be enforced at multiple layers - DB RLS, repository filters, signed widget tokens, origin checks, audit logging, and redaction - because CORS alone is not security.
- **Timeline**: The project needs a convincing end-to-end demo by the end of the week, so scope must fit a short build window.
- **Architecture**: Keep the serving stack lean - no training framework in production containers, and no giant local model dependency for the runtime.
- **Operations**: The system must be reproducible with Docker Compose and enforce quality gates in GitHub Actions.
- **Product**: The public assistant must support knowledge answers, lead capture, and escalation, not just free-form chat.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Router-first, agent-second flow | Reduces latency and cost while keeping the agent for genuinely hard turns | Pending |
| DB Row-Level Security plus repository scoping | Defense in depth against cross-tenant leaks | Pending |
| Signed, short-lived widget token with origin validation | CORS is not enough to secure the widget surface | Pending |
| Lean model-serving stack with exported artifacts | Avoids torch/runtime bloat and keeps Docker builds fast | Pending |
| Platform rails are immutable; tenant rails are configurable | Tenants can customize behavior without weakening the security floor | Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-25 after initialization*
