# Repository Structure

This is the simple repository map. The canonical workflow guide is [docs/ARCHITECTURE_AND_WORKFLOW.md](ARCHITECTURE_AND_WORKFLOW.md).

## Top-Level Layout

- `apps/` - deployable app slices and runtime entrypoints
  - `api/` - platform-spine smoke image
  - `widget/` - widget source slice for the future app split
  - `admin/` - admin source slice for the future app split
  - `modelserver/` - model-serving shell
  - `guardrails/` - guardrails shell
- `backend/` - current API runtime and widget bundle host
- `admin/` - current Streamlit admin runtime
- `widget/` - standalone React widget package and Docker image
- `services/` - shared domain logic for routing, RAG, agent, guardrails, and embeddings
- `infrastructure/` - migrations, Redis/Vault/MinIO notes, and Docker guidance
- `packages/` - shared contracts and interfaces
- `prompts/` - prompt assets
- `evals/` - quality gates and red-team suites
- `tests/` - automated verification
- `scripts/` - bootstrap and verification scripts
- `docs/` - stable human-readable docs
- `.planning/` - project state and roadmap
- `.github/workflows/` - CI, eval, and release automation

## Ownership

- Owner A / Hanan: `infrastructure/postgres/`, `infrastructure/vault/`, `infrastructure/redis/`, `infrastructure/minio/`, `apps/api/app/core/`, `apps/api/app/db/`
- Owner B / Mohammad: `services/router/`, `services/rag/`, `services/agent/`, `services/embeddings/`, `prompts/`, `evals/rag/`, `evals/agent/`
- Owner C / Rayan: `apps/modelserver/`, `services/guardrails/`, `evals/classifier/`, `evals/redteam/`, `tests/security/`
- Owner D / Ali Faddel: `apps/widget/`, `apps/admin/`, `.github/workflows/`, `scripts/`

## Docker Coverage

- `backend/Dockerfile` - legacy API + widget static bundle host
- `admin/Dockerfile` - Streamlit admin runtime
- `widget/Dockerfile` - standalone widget runtime image
- `apps/api/Dockerfile` - platform-spine smoke image
- `apps/modelserver/Dockerfile` - model-server runtime image
- `apps/guardrails/Dockerfile` - guardrails runtime image
