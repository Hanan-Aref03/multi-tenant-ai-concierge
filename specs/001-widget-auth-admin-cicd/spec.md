# Feature Specification: Widget Auth, Admin UX & CI/CD (Owner D)

**Feature Branch**: `001-widget-auth-admin-cicd`

**Created**: 2026-05-25

**Status**: Draft

**Input**: Owner D vertical slice for the Concierge multi-tenant AI SaaS (Week 8 AIE program) — Widget Auth, Admin UX, CI/CD pipeline.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Visitor Sends an Authenticated Chat Message (Priority: P1)

A visitor lands on a business's public website where the Concierge widget is embedded. The host site has pasted a single `<script>` tag. The loader automatically exchanges the public widget identifier for a short-lived session token, then opens the chat iframe. Every message the visitor sends carries that token. The backend trusts the token to identify which tenant is being served — it never trusts anything the visitor typed.

**Why this priority**: This is the core runtime path. Without authenticated widget sessions, the product cannot run at all. Isolation depends entirely on the token being the sole source of `tenant_id`.

**Independent Test**: Embed the widget on a test HTML page, open the browser, type a message — confirm the backend receives it with a valid token and the correct `tenant_id`, and that removing or forging the token returns 401/403.

**Acceptance Scenarios**:

1. **Given** a host page with the correct `<script data-widget-id="...">` tag, **When** the page loads, **Then** the loader fetches a signed session token and injects the chat iframe without any manual intervention from the visitor.
2. **Given** a valid session token, **When** the visitor sends a chat message, **Then** the backend accepts it and associates it with the correct tenant's data.
3. **Given** a missing or expired session token, **When** a chat request is made (including via `curl`), **Then** the backend responds with 401.
4. **Given** a valid widget token for Tenant A, **When** a chat request claims `tenant_id = B` in its body, **Then** the backend ignores the body field and uses only the `tenant_id` from the verified token.

---

### User Story 2 — Widget Is Blocked on an Unauthorised Host (Priority: P1)

A bad actor copies the `widget_id` and tries to embed the widget on their own domain, or calls the API directly from a server with `curl`. The system must refuse the token exchange when the request origin is not on the tenant's allowlist, and must reject API calls with a stale or stolen token.

**Why this priority**: This is the core security gate. CORS alone does not prevent server-side callers. A token exchange that skips origin validation hands out valid tokens to any caller.

**Independent Test**: Make a `curl` POST to `/api/widget/token` with a known `widget_id` from an origin not on the allowlist — expect 403. Repeat with a valid token on an expired session — expect 401.

**Acceptance Scenarios**:

1. **Given** a `widget_id` and an `Origin` header not in the tenant's `allowed_origins`, **When** the token exchange endpoint is called, **Then** it returns 403 and issues no token.
2. **Given** a widget correctly embedded on an allowed host, **When** the browser loads the page, **Then** the widget loads and a token is issued normally.
3. **Given** a stale or tampered token, **When** any chat endpoint is called, **Then** the backend returns 401.
4. **Given** a widget embedded on a disallowed host, **When** the browser makes the request, **Then** the browser receives a CORS error AND the server-side handler also returns 403 (defense-in-depth).

---

### User Story 3 — Tenant Admin Configures the Widget and Agent (Priority: P2)

A tenant admin logs into the Streamlit admin panel. They can update the widget's greeting message, theme colours, and the list of origins allowed to embed it. They can toggle which agent tools are active (`rag_search`, `capture_lead`, `escalate`), set the agent persona, and configure tenant-level guardrail rules (allowed/blocked topics, refusal tone). They can also view captured leads and copy the embed snippet.

**Why this priority**: Without admin configuration, every tenant uses identical defaults. The admin page is what makes the product multi-tenant from the operator's perspective. It is not required for the widget to function, but is required for the product to be useful.

**Independent Test**: Log in as a tenant admin, change the greeting text, reload the widget on an allowed host — confirm the new greeting appears.

**Acceptance Scenarios**:

1. **Given** a logged-in tenant admin, **When** they update widget settings (greeting, theme, allowed origins), **Then** the changes are saved and reflected in the widget on next load.
2. **Given** a logged-in tenant admin, **When** they toggle a tool on or off, **Then** the agent respects that setting on subsequent conversations.
3. **Given** a logged-in tenant admin, **When** they view the leads table, **Then** they see only their own tenant's leads (never another tenant's).
4. **Given** a logged-in tenant admin, **When** they view the embed snippet, **Then** the snippet contains the correct `data-widget-id` for their tenant and is ready to copy-paste.
5. **Given** a tenant admin authenticated as Tenant A, **When** they attempt to modify Tenant B's config via direct API call, **Then** the API returns 403.

---

### User Story 4 — CI Pipeline Gates Every Merge (Priority: P2)

Every push to the repository triggers the CI pipeline. The pipeline lints, type-checks, builds Docker images, and runs six eval gates. Any gate that falls below its committed threshold blocks the merge. The pipeline is green from day one, even before the real eval logic is fully implemented, because placeholder stubs pass at their initial thresholds.

**Why this priority**: CI gates are what make the evals real. A passing demo with no CI is theatrics; a rougher demo with real gates is the assignment. The pipeline must be the source of truth for quality regressions.

**Independent Test**: Push a commit that intentionally breaks one eval — confirm the pipeline fails and blocks merge. Revert — confirm it goes green.

**Acceptance Scenarios**:

1. **Given** any push, **When** the pipeline runs, **Then** lint and type-check complete before any eval gate is attempted.
2. **Given** a classifier eval result below the committed threshold, **When** the pipeline runs, **Then** the merge is blocked.
3. **Given** any injection/cross-tenant red-team probe that is not refused, **When** the pipeline runs, **Then** the build fails (zero-tolerance gate).
4. **Given** a fresh clone of the repository, **When** the stack smoke test runs, **Then** `docker-compose up` completes successfully.
5. **Given** the pipeline skeleton on day one with placeholder stubs, **When** the pipeline runs, **Then** all gates pass and the build is green.

---

### Edge Cases

- What happens when the token exchange is called without an `Origin` header at all? (Treat as disallowed — return 403.)
- What if a tenant's `allowed_origins` list is empty? (Block all origins — widget is effectively disabled until at least one origin is configured.)
- What if the widget bundle fails to load from the CDN/MinIO? (The loader script should fail gracefully — no broken UI on the host page.)
- What if an admin saves an `allowed_origins` entry that is malformed (not a valid URL origin)? (Validate server-side and return 422 with a clear error.)
- What if a CI eval gate threshold in `eval_thresholds.yaml` is absent or malformed? (Pipeline fails with a configuration error, not a silent pass.)
- What if two browser tabs open the widget simultaneously for the same session? (Each tab gets its own token; Redis session is scoped per-conversation-id.)

---

## Requirements *(mandatory)*

### Functional Requirements

**Widget & Loader**

- **FR-001**: The system MUST serve a JavaScript loader at `/widget.js` that reads `data-widget-id` from the `<script>` tag and injects a sandboxed chat iframe.
- **FR-002**: The loader MUST exchange the `widget_id` and the current page origin for a signed, short-lived session token before rendering the iframe.
- **FR-003**: The widget iframe MUST include every chat message's session token in the `Authorization` header of API requests.
- **FR-004**: The widget MUST fetch tenant theme config (greeting text, accent colour) at load time and apply it before first render.
- **FR-005**: The widget bundle (JS + CSS) MUST be under 50 KB gzipped.

**Widget Authentication & Origin Enforcement**

- **FR-006**: The token exchange endpoint MUST validate the `Origin` header against the tenant's `allowed_origins` before issuing any token; a mismatch MUST return 403.
- **FR-007**: All chat API endpoints MUST validate the session token from the `Authorization` header; missing or invalid tokens MUST return 401.
- **FR-008**: The `tenant_id` for every chat request MUST be extracted exclusively from the verified session token — it MUST NOT be read from the request body or query parameters.
- **FR-009**: CORS response headers MUST be generated dynamically from the tenant's `allowed_origins` in the database, not from a hardcoded environment variable.
- **FR-010**: The `Content-Security-Policy: frame-ancestors` header MUST be set dynamically per tenant from the database `allowed_origins` list.
- **FR-011**: A server-side origin check MUST exist in the request handler and MUST return 403 on mismatch, independent of browser CORS enforcement.

**Admin Streamlit UI**

- **FR-012**: The admin page MUST be accessible only to users with the `tenant_admin` role and MUST scope all reads and writes to the authenticated tenant.
- **FR-013**: The admin MUST be able to view and edit: widget greeting, theme accent colour, and `allowed_origins` list.
- **FR-014**: The admin MUST be able to toggle individual agent tools (`rag_search`, `capture_lead`, `escalate`) on or off.
- **FR-015**: The admin MUST be able to set the agent persona text and tenant-level guardrail rules (allowed topics, blocked topics, refusal tone).
- **FR-016**: The admin MUST be able to view a read-only table of leads captured for their tenant.
- **FR-017**: The admin page MUST display a ready-to-copy embed snippet containing the correct `data-widget-id` for the tenant.
- **FR-018**: Config changes MUST be persisted immediately via the FastAPI admin API; the admin page MUST show confirmation or error feedback.

**CI/CD Pipeline**

- **FR-019**: The GitHub Actions pipeline MUST run on every push: lint (Python + JS), type-check, Docker image build, then eval gates.
- **FR-020**: Eval thresholds MUST be committed in `eval_thresholds.yaml`; the pipeline MUST read thresholds from that file, not from hardcoded values.
- **FR-021**: The classifier eval gate MUST fail if macro-F1 on the held-out test set falls below the committed threshold (initial: 0.75).
- **FR-022**: The agent tool-selection gate MUST fail if fewer than the committed number of golden examples pass (initial: 13 of 15).
- **FR-023**: The RAG golden-set gate MUST fail if `hit@5` or `faithfulness` fall below committed thresholds (initial: 0.8 and 0.7).
- **FR-024**: The injection/cross-tenant red-team gate MUST fail if any probe is not refused (zero-tolerance).
- **FR-025**: The redaction gate MUST fail if any fake API key appears unredacted in logs, traces, or memory.
- **FR-026**: The stack smoke test MUST verify that `docker-compose up` from a fresh clone succeeds.
- **FR-027**: Any gate regression MUST block merge (branch protection on the CI status check).
- **FR-028**: The pipeline skeleton on day one MUST be green using placeholder stubs that pass at their initial thresholds.

### Key Entities

- **Widget**: Per-tenant embeddable chat UI. Has `widget_id` (public), `tenant_id`, `greeting`, `accent_colour`, `allowed_origins[]`.
- **WidgetSession**: Short-lived token record. Has `token`, `tenant_id`, `widget_id`, `origin`, `expires_at`, `conversation_id`.
- **TenantConfig**: Per-tenant agent + guardrail settings. Has `agent_persona`, `enabled_tools[]`, `allowed_topics[]`, `blocked_topics[]`, `refusal_tone`.
- **Lead**: Captured visitor lead. Has `tenant_id`, `visitor_name`, `contact`, `intent`, `captured_at`.
- **EvalThreshold**: CI gate threshold record committed in `eval_thresholds.yaml`. Has `gate_name`, `metric`, `threshold`, `comparison`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A visitor on an allowed host completes a chat session — from widget load to receiving an agent reply — in under 3 seconds (excluding LLM inference time).
- **SC-002**: A `curl` request with no token, an expired token, or a token for a different tenant is rejected 100% of the time across 100 test probes.
- **SC-003**: A `curl` token exchange from an origin not in `allowed_origins` is rejected 100% of the time across 100 test probes.
- **SC-004**: The widget bundle loads on the host page in under 1 second on a standard broadband connection.
- **SC-005**: A tenant admin can update widget settings and see changes reflected in the live widget within 5 seconds of saving.
- **SC-006**: All six CI eval gates run to completion on every push; a deliberate regression in any gate blocks the merge within the CI run.
- **SC-007**: The pipeline is green on day one (placeholder stub mode) before any real eval data exists.
- **SC-008**: Zero cross-tenant data exposures across all red-team CI probes.

---

## Assumptions

- The FastAPI backend (Owner A's slice) provides the auth middleware, tenant model, RLS session variable, and JWT signing infrastructure. Owner D builds on top of these — not from scratch.
- The Streamlit admin page authenticates via the same JWT flow as the FastAPI backend (no separate auth system).
- The widget is served from the same FastAPI process or from MinIO/CDN with proper cache headers; no separate widget CDN infrastructure is required for this week.
- Widget sessions are anonymous — no visitor login. The `tenant_id` comes only from the verified per-widget token, not from any user session.
- Redis for session storage and `eval_thresholds.yaml` for CI thresholds are already agreed team conventions.
- The GitHub repository is the shared team repo; CI is GitHub Actions. Branch protection rules must be enabled for the gate-blocks-merge requirement to hold.
- The "placeholder stub" approach for day-one CI means eval scripts exist and run but return hardcoded passing results until real model/data artifacts are available.
- Mobile responsiveness of the widget is a nice-to-have for this week; the primary target is desktop browsers.
