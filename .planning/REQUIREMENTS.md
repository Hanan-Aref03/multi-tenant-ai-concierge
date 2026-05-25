# Requirements: multi-tenant-ai-concierge

**Defined:** 2026-05-25
**Core Value:** Tenant A must never be able to access Tenant B data, even if a developer forgets a filter or a prompt becomes adversarial.

## v1 Requirements

Requirements for the initial release. Each maps to roadmap phases.

### Tenant and Access

- [ ] **TENA-01**: A business can create a tenant workspace with a unique tenant identity.
- [ ] **TENA-02**: A tenant admin can create or invite internal users for that tenant.
- [ ] **TENA-03**: A platform operator can provision, suspend, and delete tenants through a controlled maintenance path.
- [ ] **TENA-04**: Every request is bound to the correct tenant before data is read or written.
- [ ] **TENA-05**: Cross-tenant access attempts are rejected for tenant users, widget visitors, and agents.

### Knowledge and Retrieval

- [ ] **KNOW-01**: Tenant admins can upload FAQs, docs, policies, and service content.
- [ ] **KNOW-02**: Uploaded content is chunked and indexed for tenant-scoped retrieval.
- [ ] **KNOW-03**: Tenant admins can update or remove content and the index stays in sync.
- [ ] **KNOW-04**: Assistant answers can be grounded in tenant-owned content only.

### Widget and Visitor Access

- [ ] **WIDG-01**: Businesses can embed a public chat widget with a reusable loader/snippet.
- [ ] **WIDG-02**: Widget sessions use a short-lived signed tenant-scoped token.
- [ ] **WIDG-03**: Widget requests are accepted only from allowed origins and rejected when the token is expired or invalid.
- [ ] **WIDG-04**: Visitors can continue a conversation on the public site within the tenant's session.

### Routing and Assistant Actions

- [ ] **ROUT-01**: Inbound messages are classified into easy-handled and hard-handled turns.
- [ ] **ROUT-02**: Easy turns are answered without invoking the agent.
- [ ] **ROUT-03**: Hard turns are handed to a bounded tool-calling agent.
- [ ] **ROUT-04**: The agent can call only `rag_search`, `capture_lead`, and `escalate`.
- [ ] **ROUT-05**: The agent can save lead details for the current tenant.
- [ ] **ROUT-06**: The agent can escalate a conversation to a human or ticket when it cannot help.
- [ ] **ROUT-07**: Agent loops are capped so every turn ends safely.

### Safety and Privacy

- [ ] **SAFE-01**: Platform guardrails detect and refuse prompt injection and jailbreak attempts.
- [ ] **SAFE-02**: The system redacts PII and secrets before they reach logs, traces, or memory.
- [ ] **SAFE-03**: Tenant-configurable persona, topic, and tool settings cannot weaken platform-level safety rules.
- [ ] **SAFE-04**: The system emits audit logs for provisioning, deletion, and other security-sensitive actions.
- [ ] **SAFE-05**: Per-tenant rate limiting protects the public widget and APIs from abuse.
- [ ] **SAFE-06**: Right-to-erasure removes tenant data from Postgres, pgvector, Redis, and MinIO.

### Delivery and Evaluation

- [ ] **OPS-01**: The team can run the full stack locally with Docker Compose.
- [ ] **OPS-02**: CI runs linting, type checking, builds, and eval gates on every push.
- [ ] **OPS-03**: OpenTelemetry traces are available for widget, router, retrieval, and agent paths.
- [ ] **OPS-04**: The model server serves exported lean artifacts and verifies artifact integrity before boot.

## v2 Requirements

Deferred to a future release. Tracked now so they do not get rediscovered as surprise scope.

### Platform Expansion

- **BILL-01**: Tenant billing and subscription management.
- **IAM-01**: SSO/SAML or OAuth enterprise login for tenant users.
- **INTG-01**: Native CRM and ticketing integrations.
- **ANAL-01**: Rich analytics dashboards for tenant owners.
- **LANG-01**: Multi-language assistant behavior and widget localization.
- **SCALE-01**: Multi-region failover and active-active deployment.

## Out of Scope

Explicitly excluded for v1.

| Feature | Reason |
|---------|--------|
| Training or fine-tuning large foundation models in production | The brief explicitly favors lean serving plus hosted APIs, and training would slow the project down. |
| Native mobile apps | The assignment is web-first with an embeddable widget and admin dashboard. |
| Full CRM or ticketing product | Lead capture and escalation are enough for v1. |
| Multi-region active-active infrastructure | Too much operational overhead for a one-week demo. |
| Replacing the assistant with a fully autonomous support bot | The router/agent split is intentional so humans stay in the loop for hard cases. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TENA-01 | Phase 1 | Pending |
| TENA-02 | Phase 1 | Pending |
| TENA-03 | Phase 1 | Pending |
| TENA-04 | Phase 1 | Pending |
| TENA-05 | Phase 1 | Pending |
| KNOW-01 | Phase 2 | Pending |
| KNOW-02 | Phase 2 | Pending |
| KNOW-03 | Phase 2 | Pending |
| KNOW-04 | Phase 2 | Pending |
| WIDG-01 | Phase 3 | Pending |
| WIDG-02 | Phase 3 | Pending |
| WIDG-03 | Phase 3 | Pending |
| WIDG-04 | Phase 3 | Pending |
| ROUT-01 | Phase 4 | Pending |
| ROUT-02 | Phase 4 | Pending |
| ROUT-03 | Phase 4 | Pending |
| ROUT-04 | Phase 4 | Pending |
| ROUT-05 | Phase 4 | Pending |
| ROUT-06 | Phase 4 | Pending |
| ROUT-07 | Phase 4 | Pending |
| SAFE-01 | Phase 5 | Pending |
| SAFE-02 | Phase 5 | Pending |
| SAFE-03 | Phase 5 | Pending |
| SAFE-04 | Phase 1 | Pending |
| SAFE-05 | Phase 3 | Pending |
| SAFE-06 | Phase 5 | Pending |
| OPS-01 | Phase 1 | Pending |
| OPS-02 | Phase 5 | Pending |
| OPS-03 | Phase 5 | Pending |
| OPS-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ok

---
*Requirements defined: 2026-05-25*
*Last updated: 2026-05-25 after initial definition*
