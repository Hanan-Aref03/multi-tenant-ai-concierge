# Tasks: Widget Auth, Admin UX & CI/CD (Owner D)

**Input**: Design documents from `specs/001-widget-auth-admin-cicd/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/widget-api.md, contracts/ci-pipeline.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependency)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create project skeleton and CI skeleton — Day-1 first move. Both must be green before any other work.

- [x] T001 Create directory structure: widget/, admin/, evals/, .github/workflows/ at repo root
- [x] T002 Initialize Vite + React + TypeScript project in widget/ (`npm create vite@latest widget -- --template react-ts`)
- [x] T003 [P] Initialize Streamlit admin: create admin/requirements.txt (streamlit, requests, pyjwt) and admin/app.py stub
- [x] T004 [P] Create eval_thresholds.yaml at repo root with initial thresholds per contracts/ci-pipeline.md schema
- [x] T005 Create .github/workflows/ci.yml skeleton with stub mode — all gates pass, pipeline green on first push

**Checkpoint**: `npm run dev` in widget/ shows hello-world. CI pipeline is green on push. Day-1 first move complete.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB migrations, token service, and origin check dependency — must exist before any endpoint can be built.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Create Alembic migration for `widgets` table (id, tenant_id, widget_id, greeting, accent_colour, allowed_origins[]) in backend/alembic/versions/002_widgets.py
- [x] T007 [P] Create Alembic migration for `widget_sessions` table (id, tenant_id, widget_id, conversation_id, origin, issued_at, expires_at, revoked) in backend/alembic/versions/003_widget_sessions.py
- [x] T008 [P] Create Alembic migration for `tenant_config` table (tenant_id, agent_persona, enabled_tools[], allowed_topics[], blocked_topics[], refusal_tone) in backend/alembic/versions/004_tenant_config.py
- [x] T009 Implement Widget SQLAlchemy model in backend/app/models/widget.py (fields per data-model.md, RLS-annotated)
- [x] T010 [P] Implement WidgetSession SQLAlchemy model in backend/app/models/widget_session.py
- [x] T011 [P] Implement TenantConfig SQLAlchemy model in backend/app/models/tenant_config.py
- [x] T012 Implement JWT issue + verify service in backend/app/services/widget_token.py: `issue_widget_token(tenant_id, widget_id, conversation_id, origin) -> str` and `verify_widget_token(token) -> dict`
- [x] T013 Implement origin check dependency in backend/app/services/origin_check.py: `verify_origin(widget_id, origin)` — DB lookup, Redis cache TTL 60s, raises HTTPException(403) on mismatch
- [x] T014 Implement dynamic CORS + CSP middleware in backend/app/middleware/cors_dynamic.py: reads allowed_origins from DB per tenant, sets Access-Control-Allow-Origin and Content-Security-Policy: frame-ancestors headers

**Checkpoint**: Foundation ready — models exist, JWT service works, origin check dependency is injectable.

---

## Phase 3: User Story 1 — Visitor Sends an Authenticated Chat Message (Priority: P1) 🎯 MVP

**Goal**: A visitor on an allowed host exchanges widget_id for a JWT, and every chat message they send is authenticated and tenant-scoped via that token.

**Independent Test**: Embed widget on test/embed-test.html, open browser, type a message — backend receives it with valid token and correct tenant_id. Removing the token returns 401.

### Implementation for User Story 1

- [x] T015 [US1] Implement `POST /api/widget/token` in backend/app/api/widget.py: calls verify_origin dependency, issues JWT, inserts WidgetSession row, sets Redis session key
- [x] T016 [US1] Implement `GET /api/widget/{widget_id}/config` in backend/app/api/widget.py: returns greeting and accent_colour (no auth, cached)
- [x] T017 [US1] Implement widget JWT auth middleware in backend/app/middleware/widget_auth.py: verifies Authorization Bearer token on every chat request, extracts tenant_id from claims, raises 401 on invalid/missing
- [x] T018 [US1] Implement `POST /api/chat` stub in backend/app/api/chat.py: accepts message + conversation_id, validates token via middleware, returns placeholder reply (full agent wired by Owner B)
- [x] T019 [P] [US1] Create widget/src/api.ts: typed fetch wrapper that sends Authorization: Bearer {token} on every chat request; token stored in module state
- [x] T020 [P] [US1] Create widget/src/ChatWindow.tsx: chat UI component (message list + input box + send button)
- [x] T021 [US1] Create widget/src/App.tsx: on mount, reads token from URL params, calls GET /config, renders ChatWindow with theme applied
- [x] T022 [US1] Create widget/public/loader.js: reads data-widget-id from script tag, POSTs to /api/widget/token with window.location.origin, creates iframe on success, fails silently on error
- [x] T023 [US1] Configure FastAPI to serve /widget.js from widget/public/loader.js and serve widget dist/ as static files under /widget/
- [x] T024 [US1] Create widget/test/embed-test.html: a bare HTML page with the script tag pointing to localhost, used for manual embed flow verification

**Checkpoint**: Visitor sends chat from embed-test.html, token flow works end-to-end, 401 returned without token. User Story 1 independently functional.

---

## Phase 4: User Story 2 — Widget Blocked on Unauthorised Host (Priority: P1)

**Goal**: A request from an origin not in allowed_origins is rejected with 403 at token exchange. A stale or tampered token is rejected with 401. CORS headers are defense-in-depth, not the auth boundary.

**Independent Test**: `curl -H "Origin: https://attacker.com" POST /api/widget/token` → 403. `curl POST /api/chat` with no token → 401. Widget on allowed host still works.

### Implementation for User Story 2

- [x] T025 [US2] Wire `verify_origin` dependency into `POST /api/widget/token` handler in backend/app/api/widget.py (dependency injection, not inline)
- [x] T026 [US2] Add server-side origin validation inside `POST /api/widget/token` handler: if Origin header absent → 403; if allowed_origins list empty → 403
- [x] T027 [P] [US2] Implement Redis CORS cache layer in backend/app/services/origin_check.py: cache key `widget_origins:{widget_id}`, TTL 60s, auto-invalidated on admin update
- [x] T028 [P] [US2] Implement Content-Security-Policy: frame-ancestors header builder in backend/app/middleware/cors_dynamic.py: builds header string from allowed_origins list per tenant
- [x] T029 [US2] Wire widget_auth middleware to reject missing, expired, and tampered tokens with 401 — confirm tenant_id is never taken from request body in backend/app/api/chat.py
- [x] T030 [US2] Write pytest tests for origin enforcement in backend/tests/test_widget_auth.py: test 403 on disallowed origin, 403 on missing Origin header, 401 on missing token, 401 on expired token, 200 on allowed origin + valid token

**Checkpoint**: All test_widget_auth.py tests pass. curl from attacker.com → 403. curl with no token → 401. Allowed host still works.

---

## Phase 5: User Story 3 — Tenant Admin Configures the Widget and Agent (Priority: P2)

**Goal**: A logged-in tenant admin can update widget settings, toggle tools, set persona and guardrails, view leads, and copy the embed snippet — all scoped to their tenant only.

**Independent Test**: Log in as tenant admin, change greeting text, reload widget on allowed host — new greeting appears. Admin from Tenant A cannot read Tenant B's leads.

### Implementation for User Story 3

- [x] T031 [US3] Implement `GET /api/admin/widget` and `PUT /api/admin/widget` in backend/app/api/admin.py: role=tenant_admin guard, RLS-scoped reads/writes, invalidates Redis cache on PUT
- [x] T032 [P] [US3] Implement `GET /api/admin/config` and `PUT /api/admin/config` in backend/app/api/admin.py: returns/updates TenantConfig row for this tenant; validates enabled_tools and refusal_tone values
- [x] T033 [P] [US3] Implement `GET /api/admin/leads` in backend/app/api/admin.py: paginated read-only query on leads table, RLS-scoped to tenant, returns visitor_name, contact, intent, captured_at
- [x] T034 [US3] Create admin/api_client.py: typed Python wrapper for all admin API endpoints, reads JWT from st.session_state, handles 401/403 with clear error messages
- [x] T035 [US3] Create admin/app.py: Streamlit login form (email + password → POST /api/auth/login → store JWT in st.session_state), page routing to widget_config / agent_config / leads
- [x] T036 [P] [US3] Create admin/pages/widget_config.py: form fields for greeting, accent_colour, allowed_origins list; PUT /api/admin/widget on save; displays embed snippet `<script src="/widget.js" data-widget-id="..."></script>`
- [x] T037 [P] [US3] Create admin/pages/agent_config.py: text area for agent_persona, checkboxes for enabled_tools, text inputs for allowed_topics/blocked_topics, dropdown for refusal_tone; PUT /api/admin/config on save
- [x] T038 [P] [US3] Create admin/pages/leads.py: read-only st.dataframe showing leads from GET /api/admin/leads with pagination

**Checkpoint**: Admin saves new greeting → widget shows updated greeting within 5s. Leads page shows only this tenant's data. Cross-tenant PUT attempt returns 403.

---

## Phase 6: User Story 4 — CI Pipeline Gates Every Merge (Priority: P2)

**Goal**: Every push triggers lint + build + six eval gates. Any gate regression blocks merge. Pipeline is green from day one in stub mode.

**Independent Test**: Push a commit that sets classifier threshold to 0.99 (guaranteed fail) — pipeline fails. Revert — pipeline goes green.

### Implementation for User Story 4

- [x] T039 [US4] Create evals/_common.py: YAML threshold loader (`load_thresholds(path) -> dict`), stub mode detection (`--stub` flag or `CI_STUB_MODE` env var), stdout JSON reporter, exit code rules (0=pass, 1=fail, 2=config error)
- [x] T040 [P] [US4] Create evals/classifier.py: loads threshold from eval_thresholds.yaml, in stub mode returns threshold value exactly + exits 0, in real mode runs classifier eval and compares macro-F1 vs threshold
- [x] T041 [P] [US4] Create evals/agent_tool_selection.py: stub mode exits 0 with 13/15 pass; real mode loads golden set from evals/data/agent_golden.json and runs agent tool selection check
- [x] T042 [P] [US4] Create evals/rag.py: stub mode exits 0 with hit@5=0.8, faithfulness=0.7; real mode loads 15 triples from evals/data/rag_golden.json
- [x] T043 [P] [US4] Create evals/injection_redteam.py: stub mode exits 0 with 10/10 refused; real mode loads probes from evals/data/redteam_probes.json and tests each against the guardrails endpoint
- [x] T044 [P] [US4] Create evals/redaction.py: stub mode exits 0; real mode checks log output for test API key pattern `sk-test-[0-9a-f]{32}` and fails if found unredacted
- [x] T045 [US4] Create evals/data/ directory with placeholder golden set files: agent_golden.json (15 examples, all pass), rag_golden.json (15 triples), redteam_probes.json (10 probes, all refused in stub)
- [x] T046 [US4] Update .github/workflows/ci.yml with full pipeline: lint job (ruff + eslint), build-images job, eval-gates matrix job (reads CI_STUB_MODE=true initially), smoke-test job
- [x] T047 [US4] Create .env.example with all required env vars (DATABASE_URL, REDIS_URL, VAULT_TOKEN, OPENAI_API_KEY, SECRET_KEY) — smoke test copies this file

**Checkpoint**: All 6 CI gates pass in stub mode. Lowering classifier threshold to 0.99 in eval_thresholds.yaml causes gate failure. Revert restores green.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verification, documentation, and hardening across all user stories.

- [x] T048 [P] Verify widget bundle size: add `npm run size` script to widget/package.json that builds and checks gzip size < 50KB; run in CI
- [x] T049 [P] Add integration test for full embed flow in backend/tests/test_widget_embed.py: token exchange → chat → 401 on bad token (uses pytest + httpx)
- [x] T050 Run quickstart.md verification checklist manually and fix any gaps
- [x] T051 [P] Create SECURITY.md section documenting widget auth threat model: CORS-is-not-auth, token-is-the-boundary, tenant_id-from-token-only
- [x] T052 [P] Add .dockerignore for widget/ and admin/ to keep images lean (exclude node_modules, __pycache__, .git)
- [x] T053 Add Dockerfile for admin/ (python:3.11-slim, streamlit, no torch) in admin/Dockerfile
- [x] T054 Add widget build step to docker-compose so widget dist/ is served by the API container

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. Day-1 first move.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational — the happy path.
- **US2 (Phase 4)**: Depends on US1 completion — hardens the same endpoints.
- **US3 (Phase 5)**: Depends on Foundational — independent of US1/US2.
- **US4 (Phase 6)**: Can start from Setup completion — CI skeleton done in Phase 1 T005; eval scripts are independent.
- **Polish (Phase 7)**: Depends on all user stories complete.

### User Story Dependencies

- **US1 (P1)**: Start after Foundational — no story dependencies.
- **US2 (P1)**: Start after US1 — hardens the same `/api/widget/token` and `/api/chat` endpoints.
- **US3 (P2)**: Start after Foundational — fully parallel with US1/US2 (different endpoints and files).
- **US4 (P2)**: Skeleton in Phase 1, scripts in Phase 6 — parallel with all user stories.

### Within Each User Story

- DB migrations (T006–T008) before SQLAlchemy models (T009–T011)
- Models before services (T012–T014)
- Services before API endpoints (T015–T018)
- API endpoints before frontend (T019–T024)
- US2 hardens US1 endpoints — complete US1 first

### Parallel Opportunities

Within **Phase 2** (can run in parallel): T007, T008, T010, T011, T013, T014
Within **US1** (can run in parallel): T019 (api.ts) and T020 (ChatWindow.tsx)
Within **US3** (can run in parallel): T032, T033, T036, T037, T038
Within **US4** (can run in parallel): T040, T041, T042, T043, T044
**US3** and **US4** scripts fully parallel with US1/US2 work

---

## Parallel Execution Examples

### Phase 2 Foundational — launch together:
```
Task T007: Create widget_sessions migration
Task T008: Create tenant_config migration
Task T010: Implement WidgetSession model
Task T011: Implement TenantConfig model
Task T013: Implement origin_check.py service
Task T014: Implement cors_dynamic.py middleware
```

### US3 Admin pages — launch together after T035:
```
Task T036: admin/pages/widget_config.py
Task T037: admin/pages/agent_config.py
Task T038: admin/pages/leads.py
```

### US4 Eval scripts — launch together after T039:
```
Task T040: evals/classifier.py
Task T041: evals/agent_tool_selection.py
Task T042: evals/rag.py
Task T043: evals/injection_redteam.py
Task T044: evals/redaction.py
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001–T005) — CI green, widget hello-world ✓
2. Complete Phase 2: Foundational (T006–T014) — models, token service, origin check ✓
3. Complete Phase 3: US1 (T015–T024) — full token exchange + widget embed flow ✓
4. **STOP and VALIDATE**: Run embed-test.html, confirm 401 without token
5. Demo: widget loads, chats, is rejected without token

### Incremental Delivery

1. Setup + Foundational → skeleton green
2. US1 → token auth + widget embed (MVP demo-able)
3. US2 → origin blocking hardened (security complete)
4. US3 → admin config page (full product)
5. US4 → real CI gates (graded artifact)

### Parallel Team Strategy

With more capacity:

- **Track A**: US1 → US2 (widget auth, backend endpoints)
- **Track B**: US3 (Streamlit admin, concurrent with US1)
- **Track C**: US4 eval scripts (concurrent with everything after T005)

---

## Notes

- [P] tasks operate on different files — run in parallel safely
- [US1]–[US4] labels map tasks to spec.md user stories for traceability
- **Critical rule**: `tenant_id` must NEVER be read from request body — only from verified JWT claims
- **Day-1 goal**: T001–T005 complete, CI green, widget hello-world served
- Commit after each phase checkpoint
- Run `quickstart.md` verification checklist after Phase 7
