# Concierge Demo Runbook

This is the shortest reliable path to run the project end to end and show the chatbot live.

## 1. Set Up Secrets

Make sure your `.env` has the real local-dev values you want to use:

- `GEMINI_API_KEY` for the assistant fallback / LLM path
- `SERVICE_TOKEN` for service-to-service auth
- `WIDGET_ALLOWED_ORIGINS` including the origin you will use for the embed test page

If you only want the local demo behavior, the rest of the values can stay on the defaults from `.env.example`.

## 2. Start The Whole Stack

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_app.ps1
```

Expected result:

- API on `http://localhost:8000`
- Admin on `http://localhost:8501`
- Model server on `http://localhost:8010`
- Guardrails on `http://localhost:8011`

## 3. Serve The Widget Test Page

Open a second terminal and run:

```powershell
python -m http.server 5500 --directory widget\test
```

Then open:

```text
http://localhost:5500/embed-test.html
```

If you use a different port, add that origin to the widget allowlist in the admin page first.

## 4. Demo Flow

Follow this order when you present the project:

1. Open the admin page and show the tenant widget config.
2. Confirm the embed snippet includes `data-api-base="http://localhost:8000"`.
3. Open the embed test page from the local HTTP server.
4. Send a normal message like `hello`.
5. Send a knowledge-style question like `what are your business hours?`.
6. Send a lead-style message like `I want a demo.`
7. Show the origin check by removing the test origin and refreshing.
8. Show the token check by reusing an expired token or no token.

## 5. What Working Looks Like

- The widget loads without crashing the host page.
- The widget gets a short-lived signed token.
- `/api/chat` accepts the valid token and returns a reply.
- The reply no longer comes from the old stub.
- Tenant identity stays inside the token and never comes from the request body.

## 6. Useful Direct Checks

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8010/healthz
Invoke-RestMethod http://localhost:8011/healthz
Invoke-RestMethod http://localhost:8000/api/admin/widget
Invoke-RestMethod http://localhost:8000/api/admin/config
```

## 7. If The Chat Falls Back

If the chatbot only gives a generic handoff reply:

- check that `GEMINI_API_KEY` is present in `.env`
- check that `SERVICE_TOKEN` matches between the API and modelserver/guardrails containers
- check the backend logs for classifier, RAG, or agent warnings
- confirm the widget origin is on the allowlist

The important part for the demo is that the flow stays safe and does not crash.
