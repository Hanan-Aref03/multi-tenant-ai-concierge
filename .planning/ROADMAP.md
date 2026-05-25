# Roadmap: multi-tenant-ai-concierge

**Execution style:** Standard/horizontal layering with vertical validation at each step.
**Cadence:** 5-day sprint aligned to the brief's Monday-through-Friday build window.
**Team principle:** One primary owner per phase, with at least one supporting reviewer from another discipline.
**Owner map:** Owner A = Hanan, Owner B = Mohammad, Owner C = Rayan, Owner D = Ali Faddel.

| # | Phase | Day | Lead | Goal | Requirements |
|---|-------|-----|------|------|--------------|
| 1 | Platform Spine | Day 1 | Mohammad | Establish secure tenant bootstrap, auth, RLS, audit logging, and a reproducible local stack. | TENA-01..05, SAFE-04, OPS-01 |
| 2 | Knowledge Layer | Day 2 | Hanan | Build tenant-scoped content ingestion, chunking, indexing, and retrieval. | KNOW-01..04 |
| 3 | Widget Surface | Day 3 | Ali Faddel | Ship the embeddable widget, signed token flow, origin checks, session continuity, and rate limiting. | WIDG-01..04, SAFE-05 |
| 4 | Router and Agent | Day 4 | Hanan | Add classifier routing, bounded tool-calling, lead capture, escalation, and lean model serving. | ROUT-01..07, OPS-04 |
| 5 | Hardening and Release | Day 5 | Rayan | Lock in guardrails, redaction, traces, CI eval gates, and erasure so the demo is safe and reproducible. | SAFE-01..03, SAFE-06, OPS-02..03 |

## Phase Details

### Phase 1: Platform Spine
**Goal:** Create the secure foundation: tenant provisioning, auth, database isolation, audit logging, and a one-command local environment.
**Lead:** Mohammad
**Support:** Hanan for architecture review, Ali Faddel for repo/CI scaffolding
**Requirements:** TENA-01, TENA-02, TENA-03, TENA-04, TENA-05, SAFE-04, OPS-01
**Success Criteria:**
1. A new tenant can be provisioned with a first admin and has a unique tenant identity.
2. Cross-tenant read and write attempts fail in tests even when the application layer forgets to scope a query.
3. Provision, suspend, and delete actions are audit-logged.
4. `docker compose up` starts the core services the team needs for the rest of the work.

### Phase 2: Knowledge Layer
**Goal:** Turn tenant content into a tenant-scoped knowledge base that the assistant can reliably search and answer from.
**Lead:** Hanan
**Support:** Mohammad for security boundaries, Rayan for evaluation contract
**Requirements:** KNOW-01, KNOW-02, KNOW-03, KNOW-04
**Success Criteria:**
1. Tenant admins can upload content types from the brief and see them ingested successfully.
2. Content is chunked, embedded, and indexed only for the owning tenant.
3. Updating or deleting content updates retrieval behavior instead of leaving stale answers behind.
4. Retrieval-backed answers can be demonstrated against the tenant's own knowledge base.

### Phase 3: Widget Surface
**Goal:** Ship the public widget and its auth path so visitors can chat safely from an embedded surface.
**Lead:** Ali Faddel
**Support:** Mohammad for token/origin enforcement, Hanan for API contract alignment
**Requirements:** WIDG-01, WIDG-02, WIDG-03, WIDG-04, SAFE-05
**Success Criteria:**
1. The widget can be embedded with a reusable loader/snippet on a public site.
2. Widget access requires a short-lived signed tenant-scoped token and rejects expired or malformed tokens.
3. Disallowed origins are blocked server-side, not just by browser policy.
4. Visitor conversations persist within the tenant session without crossing tenant boundaries.
5. Per-tenant rate limiting is observable in the API path.

### Phase 4: Router and Agent
**Goal:** Add the workflow router and the bounded agent so easy questions stay cheap and hard questions can act safely.
**Lead:** Hanan
**Support:** Rayan for classifier/model serving, Mohammad for lead persistence and escalation records
**Requirements:** ROUT-01, ROUT-02, ROUT-03, ROUT-04, ROUT-05, ROUT-06, ROUT-07, OPS-04
**Success Criteria:**
1. The router can separate easy turns from hard turns consistently.
2. Easy turns are answered without invoking the agent.
3. Hard turns invoke an agent that can call only `rag_search`, `capture_lead`, and `escalate`.
4. Lead capture and escalation are written to the correct tenant records.
5. The lean model server starts from an exported artifact and fails fast if the artifact integrity check does not pass.

### Phase 5: Hardening and Release
**Goal:** Make the system safe to demo: guardrails are strict, traces are visible, CI fails on regressions, and erasure works end-to-end.
**Lead:** Rayan
**Support:** All teammates, with Ali on CI wiring and Hanan on integration review
**Requirements:** SAFE-01, SAFE-02, SAFE-03, SAFE-06, OPS-02, OPS-03
**Success Criteria:**
1. Prompt injection and jailbreak attempts are blocked by platform rails.
2. PII and secrets are redacted before they can leak into logs, traces, or memory.
3. CI runs linting, type checks, builds, and eval gates on every push and blocks regressions.
4. OpenTelemetry traces make widget, router, retrieval, and agent paths easy to inspect.
5. Right-to-erasure removes tenant data from Postgres, pgvector, Redis, and MinIO.
6. The final demo can show tenant isolation, widget security, routing, lead capture, escalation, and the main evaluation metrics.

## Delivery Notes

- This roadmap is intentionally vertical enough to demo every day, but horizontal enough to let the team work in parallel without tripping over each other.
- Each phase should end with a short integration check so that bugs do not accumulate until Friday.
- The most important red-line test is still the same: try to break tenant isolation, and verify the system refuses.
