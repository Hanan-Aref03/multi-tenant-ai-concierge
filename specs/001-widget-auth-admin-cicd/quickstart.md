# Quickstart: Widget Auth, Admin UX & CI/CD (Owner D)

**Date**: 2026-05-25

---

## Prerequisites

- Docker + docker-compose installed
- Node.js 20+ and npm
- Python 3.11+
- A `.env` file (copy `.env.example` and fill in API key + Vault token)

---

## Day-1 First Move

Stand up the CI skeleton and hello-world widget — both must be green before any other Owner D work.

```bash
# 1. Serve the hello-world widget (Vite dev server)
cd widget
npm install
npm run dev
# Open http://localhost:5173 — should show "Hello from Concierge Widget"

# 2. Check the CI pipeline is green (GitHub Actions)
# Push to the repo — the skeleton pipeline with stubs should pass all gates
```

---

## Widget Development

```bash
cd widget
npm install        # install deps
npm run dev        # Vite dev server on :5173
npm run build      # production build to dist/
npm run preview    # preview production build
```

**Test the embed flow**:
```bash
# Open test/embed-test.html in a browser
# It includes <script src="http://localhost:8000/widget.js" data-widget-id="test-widget">
# The loader should: fetch a token, inject the iframe, show the greeting
```

---

## Admin Streamlit

```bash
cd admin
pip install -r requirements.txt
streamlit run app.py
# Opens http://localhost:8501
# Log in with a tenant_admin JWT (get one from the API: POST /api/auth/login)
```

---

## Backend Widget Endpoints

```bash
# Token exchange (should 403 with wrong origin)
curl -X POST http://localhost:8000/api/widget/token \
  -H "Content-Type: application/json" \
  -H "Origin: https://acme.com" \
  -d '{"widget_id": "test-widget-id"}'

# Token exchange with bad origin (must 403)
curl -X POST http://localhost:8000/api/widget/token \
  -H "Content-Type: application/json" \
  -H "Origin: https://attacker.com" \
  -d '{"widget_id": "test-widget-id"}'

# Chat with no token (must 401)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "fake", "message": "hello"}'
```

---

## Running CI Gates Locally

```bash
# Run all eval gates locally (stub mode — always pass)
CI_STUB_MODE=true python evals/classifier.py --thresholds eval_thresholds.yaml --stub
CI_STUB_MODE=true python evals/agent_tool_selection.py --thresholds eval_thresholds.yaml --stub
CI_STUB_MODE=true python evals/rag.py --thresholds eval_thresholds.yaml --stub
CI_STUB_MODE=true python evals/injection_redteam.py --thresholds eval_thresholds.yaml --stub
CI_STUB_MODE=true python evals/redaction.py --thresholds eval_thresholds.yaml --stub

# Run real gates once model artifacts exist
python evals/classifier.py --thresholds eval_thresholds.yaml
```

---

## Verification Checklist

After implementation, verify:

- [ ] `GET /widget.js` returns JavaScript, `Cache-Control: public, max-age=604800`
- [ ] `POST /api/widget/token` with disallowed origin → `403`
- [ ] `POST /api/widget/token` with allowed origin → `200` with JWT
- [ ] `POST /api/chat` with no token → `401`
- [ ] `POST /api/chat` with valid token + `tenant_id` in body → body field ignored, correct tenant used
- [ ] Widget loads on `test/embed-test.html` and shows greeting
- [ ] Widget fails silently on a page with a disallowed origin
- [ ] Admin page shows only this tenant's leads
- [ ] Admin saves new greeting → widget shows new greeting within 5 s
- [ ] CI pipeline green on first push (stub mode)
- [ ] Deliberate F1 drop below 0.75 → CI gate fails
