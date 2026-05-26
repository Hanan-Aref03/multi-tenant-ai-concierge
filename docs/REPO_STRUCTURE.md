# Repository Structure

This is the recommended full repository layout for the concierge project.

```text
multi-tenant-ai-concierge/
|-- README.md
|-- AGENTS.md
|-- .env.example
|-- .gitignore
|-- Makefile
|-- docker-compose.yml
|-- .planning/
|-- docs/
|   |-- TEAM.md
|   |-- HANAN_PLATFORM_SPINE_PLAN.md
|   `-- REPO_STRUCTURE.md
|-- apps/
|   |-- api/
|   |   |-- app/main.py
|   |   |-- app/core/config.py
|   |   |-- app/core/security.py
|   |   |-- app/core/tenant_context.py
|   |   |-- app/api/router.py
|   |   |-- app/api/v1/health.py
|   |   |-- app/api/v1/tenants.py
|   |   |-- app/api/v1/content.py
|   |   |-- app/api/v1/widget.py
|   |   |-- app/api/v1/conversations.py
|   |   |-- app/db/session.py
|   |   |-- app/db/models/tenant.py
|   |   |-- app/db/models/content.py
|   |   |-- app/db/models/conversation.py
|   |   |-- app/db/models/lead.py
|   |   |-- app/services/audit_service.py
|   |   |-- app/services/agent_service.py
|   |   `-- app/services/rag_service.py
|   |-- widget/
|   |   |-- src/main.tsx
|   |   |-- src/App.tsx
|   |   |-- src/components/ChatWidget.tsx
|   |   `-- src/lib/api.ts
|   |-- admin/
|   |   |-- app.py
|   |   |-- pages/Dashboard.py
|   |   |-- pages/Tenants.py
|   |   |-- pages/Knowledge.py
|   |   `-- pages/Guardrails.py
|   `-- modelserver/
|       |-- app/main.py
|       |-- app/classifier.py
|       |-- app/artifacts.py
|       `-- app/metrics.py
|-- services/
|   |-- router/router.py
|   |-- rag/chunking.py
|   |-- rag/retrieval.py
|   |-- agent/agent.py
|   |-- agent/tools.py
|   |-- guardrails/rails.yml
|   |-- guardrails/redaction.py
|   `-- embeddings/client.py
|-- infrastructure/
|   |-- docker/README.md
|   |-- postgres/migrations/0001_init.sql
|   |-- postgres/migrations/0002_rls.sql
|   |-- redis/config/redis.conf
|   |-- vault/policies/tenant.hcl
|   `-- minio/buckets.md
|-- packages/
|   `-- contracts/openapi.yaml
|-- prompts/
|   |-- system/base.md
|   |-- router/intent_classifier.md
|   |-- agent/tool_use.md
|   `-- guardrails/platform.md
|-- evals/
|   |-- classifier/metrics.md
|   |-- rag/metrics.md
|   |-- agent/metrics.md
|   |-- redteam/prompts.md
|   `-- release/checklist.md
|-- tests/
|   |-- security/test_tenant_isolation.py
|   |-- widget/test_widget_token.py
|   `-- integration/test_smoke.py
|-- scripts/
|   |-- bootstrap.ps1
|   |-- run_evals.ps1
|   `-- verify_isolation.ps1
`-- .github/
    `-- workflows/
        |-- ci.yml
        |-- evals.yml
        `-- release.yml
```

## Ownership

- Owner A / Hanan: `infrastructure/postgres/`, `infrastructure/vault/`, `infrastructure/redis/`, `infrastructure/minio/`, `apps/api/app/core/`, `apps/api/app/db/`
- Owner B / Mohammad: `services/router/`, `services/rag/`, `services/agent/`, `services/embeddings/`, `prompts/`, `evals/rag/`, `evals/agent/`
- Owner C / Rayan: `apps/modelserver/`, `services/guardrails/`, `evals/classifier/`, `evals/redteam/`, `tests/security/`
- Owner D / Ali Faddel: `apps/widget/`, `apps/admin/`, `.github/workflows/`, `scripts/`
