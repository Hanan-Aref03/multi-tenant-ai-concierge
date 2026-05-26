# Research: Widget Auth, Admin UX & CI/CD (Owner D)

**Phase**: 0 — Pre-Design Research
**Date**: 2026-05-25
**Feature**: specs/001-widget-auth-admin-cicd/spec.md

---

## Decision 1: Widget Embedding Pattern — iframe vs Shadow DOM

**Decision**: iframe

**Rationale**: An iframe provides hard browser-enforced style and script isolation from the host page. The widget cannot be styled over or XSS'd through the host page's CSS/JS. The loader injects a single `<iframe src="/widget/chat">` — the host page only touches `data-widget-id` on the script tag. Shadow DOM would share the origin, complicating token management.

**Alternatives considered**:
- Shadow DOM Web Component: lighter but requires careful token passing through attributes; style bleed possible.
- Full script injection: simplest bundle but no isolation from host JS; easier for attackers to intercept token.

---

## Decision 2: Widget Token Format — JWT vs HMAC

**Decision**: JWT (PyJWT, HS256)

**Rationale**: JWT is self-contained — the API can verify the token without a DB round-trip on every chat message, keeping latency low. Claims carry `tenant_id`, `widget_id`, `origin`, `exp`. PyJWT is already in the project's auth stack (fastapi-users). Token expiry is set to 30 minutes; the widget auto-refreshes before expiry.

**Alternatives considered**:
- HMAC opaque token: requires Redis lookup on every request — extra latency and Redis dependency in the hot path.
- Session cookie: requires `SameSite` / `Secure` cookie config across unknown host origins; iframe cross-origin cookie restrictions make this brittle.

---

## Decision 3: Dynamic CORS & CSP Generation

**Decision**: FastAPI middleware reads `allowed_origins` from the Postgres `widgets` table (cached in Redis, TTL 60 s) and sets `Access-Control-Allow-Origin` and `Content-Security-Policy: frame-ancestors` headers per request.

**Rationale**: Hardcoding origins in an env var means adding a new tenant origin requires a redeploy. DB-driven CORS means the admin can add an origin via the config page and it takes effect within 60 seconds. The cache TTL is a deliberate trade-off: immediate consistency vs DB load.

**Alternatives considered**:
- Env-var allowlist: simpler, but requires redeploy for tenant origin changes — unacceptable for a SaaS.
- No cache, DB on every request: eliminates the 60 s lag but adds latency and load to the CORS middleware path.

---

## Decision 4: React Widget Build Tooling — Vite vs CRA vs esbuild direct

**Decision**: Vite + React + TypeScript

**Rationale**: Vite produces the smallest output bundles out of the box and has the fastest HMR for development. TypeScript catches widget API contract mistakes at build time. The `dist/` output is a single JS + CSS file pair that the FastAPI app or MinIO can serve.

**Alternatives considered**:
- Create React App: heavier, slower build, larger output.
- esbuild direct: smallest possible but no JSX plugin DX; requires more manual config for a week-long project.

---

## Decision 5: Admin UI — Streamlit vs React

**Decision**: Streamlit (Python)

**Rationale**: Streamlit is specified by the project brief for the tenant admin page. It allows rapid form-based UI without a separate frontend build pipeline. Authentication is proxied through the same FastAPI JWT — Streamlit reads the token from `st.session_state` after a login form.

**No alternatives considered** — Streamlit is the spec-mandated choice.

---

## Decision 6: CI/CD Platform — GitHub Actions

**Decision**: GitHub Actions with matrix jobs

**Rationale**: Specified by the project brief. The workflow has four stages: (1) lint + type-check, (2) build Docker images, (3) run eval gates, (4) smoke test. Each eval gate is a separate job that reads thresholds from `eval_thresholds.yaml`. Branch protection rules tie CI status to merge eligibility.

**Eval threshold file format** (agreed team convention):

```yaml
classifier:
  metric: macro_f1
  threshold: 0.75
  comparison: ">="

agent_tool_selection:
  metric: pass_count
  total: 15
  threshold: 13
  comparison: ">="

rag:
  hit_at_5:
    threshold: 0.8
    comparison: ">="
  faithfulness:
    threshold: 0.7
    comparison: ">="

injection_redteam:
  metric: refused_count
  total: 10
  threshold: 10
  comparison: "=="   # zero tolerance

redaction:
  metric: leaked_count
  threshold: 0
  comparison: "=="   # zero tolerance
```

**Placeholder stub approach for day-one green CI**: Each eval script has a `--stub` mode (or reads an env var `CI_STUB_MODE=true`) that returns hardcoded passing results. The workflow passes `CI_STUB_MODE` only until real model artifacts exist; the variable is removed once the first real eval run lands.

---

## Decision 7: Server-Side Origin Validation Architecture

**Decision**: FastAPI dependency injected at the route level, not at the CORS middleware level.

**Rationale**: CORS middleware runs browser-side enforcement. A separate `verify_origin(request, widget_id)` FastAPI dependency on the `/api/widget/token` endpoint does the server-side check. The dependency looks up `widget_id` → `allowed_origins` in the DB (cached), compares against the `Origin` header, and raises `HTTPException(403)` on mismatch. This keeps the check explicit, testable, and impossible to bypass by misconfiguring the middleware.

**Alternatives considered**:
- Inline in route handler: works but not reusable; each new widget endpoint must remember to add the check.
- CORS middleware only: doesn't protect against non-browser callers — explicitly ruled out by the spec.

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Token lifetime | 30 minutes, auto-refresh at 5 min remaining |
| Session Redis key format | `widget_session:{conversation_id}` → TTL 30 min |
| Widget bundle entry point | `/widget/embed.html` inside iframe; loader at `/widget.js` |
| Streamlit auth | Login form in `admin/app.py`; FastAPI JWT stored in `st.session_state` |
| CSP frame-ancestors format | `Content-Security-Policy: frame-ancestors 'self' https://allowed.example.com` |
| Eval stub removal trigger | Remove `CI_STUB_MODE` env var once `model_card.json` artifact is present |
