# Mohammad's Progress Log

This document tracks the progress made by Mohammad (Owner B) on the multi-tenant-ai-concierge project.

## Initial Setup
- **Personal Action Plan**: Generated a detailed, step-by-step checklist (`MOHAMMAD_STEPS.md`) mapping out responsibilities across all 5 phases of the project.
- **Git Hygiene**: Added `MOHAMMAD_STEPS.md` to `.gitignore` to ensure personal working files are not pushed to the shared repository.

## Phase 2: Knowledge Layer

### Step 2A: Embeddings Client (`services/embeddings/client.py`)
- **Implemented Local Embeddings (Step 2A.1)**:
  - Switched from an external API strategy to a local model strategy.
  - Initialized `SentenceTransformer` using the `sentence-transformers/all-MiniLM-L6-v2` model.
  - Explicitly bound the model to `device="cpu"` to avoid CUDA dependency issues and keep the Docker footprint lean.
  - Implemented asynchronous wrappers (`embed_texts` and `embed_text`) using `asyncio.get_running_loop().run_in_executor` so that the CPU-bound embedding generation doesn't block the FastAPI event loop.
- **Implemented Redis Caching (Step 2A.2)**:
  - Modified the embeddings client to accept a `tenant_id` and a `redis_client`.
  - Added robust caching logic: hashes the incoming text using SHA-256 and generates cache keys in the format `emb:{tenant_id}:{hash[:16]}`.
  - Used Redis `mget` to check for cached embeddings in batch before passing the missed texts to the local model.
  - Used Redis `pipeline()` to efficiently store newly computed embeddings back into the cache with a 24-hour TTL (86,400 seconds).
  - Added safe fallbacks: if Redis is unavailable or errors out, the system degrades gracefully by computing embeddings live without crashing.
  - Implemented 3-try exponential backoff logic (1s, 2s, 4s) around the embedding generation to increase resilience, which is especially useful if switching to an external API like Groq later.
  - Wired up `settings.GROQ_API_KEY` dynamically within the embedding client, strictly respecting team boundaries by assuming the `config.py` loading mechanism will be fully built by Owner A (Hanan).

### Step 2B: Content Chunking (`services/rag/chunking.py`)
- **Implemented FAQ Chunking (Step 2B.2)**:
  - Wrote a custom algorithm to scan for `Q:` and `A:` (or `Question:` and `Answer:`) structures and lock them together into single, cohesive chunks so answers aren't accidentally split from their questions.
- **Implemented Text Splitting (Step 2B.1)**:
  - Created a lean, pure-Python recursive character text splitter.
  - Splits documents, policies, and service descriptions using a hierarchical separator fallback (`\n\n`, `\n`, `. `, ` `).
  - Enforces a chunk size limit of 2,000 characters (approx. ~512 tokens) with an overlap of 250 characters (approx. ~64 tokens).
  - Ensured every chunk carries secure metadata (`tenant_id`, `content_id`, `chunk_index`, `content_type`) back to the ingestion pipeline.

### Step 2D: Vector Retrieval & Reranking (`services/rag/retrieval.py`)
- **Implemented Vector Search (Step 2D.1)**:
  - Wrote query embedding pipeline integrating with `EmbeddingClient`.
  - Implemented cosine similarity database retrieval via pgvector with strict tenant-isolation filtering.
  - Added configurable score filtering (defaulting to 0.35) to discard irrelevant matches.
- **Implemented Confidence Reranking (Step 2D.2)**:
  - Wrote a post-filtering reranker applying a stricter confidence threshold (0.65) to maximize precision.
  - Implemented document deduplication keeping only the highest-scoring chunk per document to avoid LLM context redundancy.

### Step 2E: Content API Endpoints (`apps/api/app/api/v1/content.py`)
- **Created CRUD Endpoints**:
  - Implemented `POST /` to create and trigger the chunking -> embedding -> indexing pipeline.
  - Implemented `PUT /{content_id}` to update and re-index content.
  - Implemented `DELETE /{content_id}` to clean up both content, pgvector index embeddings, and associated files.
  - Implemented `GET /` to return paginated lists of documents scoped strictly to the current tenant.
- **Respected Boundaries**:
  - Built wrappers and fallbacks for dependencies owned by Hanan (`get_current_tenant_id` and `get_db`) to ensure code can run locally/mocked without modifying other members' domains.

### Step 2F: RAG Service (`apps/api/app/services/rag_service.py`)
- **Orchestrated Ingestion & Querying**:
  - Implemented `index_document()` to map raw documents to chunks, compute embeddings, and insert vector records.
  - Implemented `delete_document_index()` for idempotent cleanups.
  - Implemented `answer_from_knowledge()` to orchestrate query retrieval, reranking, system prompt building, and LLM completions.

### Step 2H: Evals (`evals/rag/`)
- **Created Golden Dataset (Step 2H.1)**:
  - Formulated a 15-question evaluation suite (`evals/rag/golden_set.json`) covering all 4 content types (faq, doc, policy, service).
  - Defined expected target document IDs and keyword validation tags for every test query.
- **Created Evaluation Suite (`evals/rag/run_evals.py`)**:
  - Implemented automatic calculation of **Hit@5** (recall), **MRR** (Mean Reciprocal Rank), **Faithfulness** (context grounding), and **Relevance** (using keyword proxy filters).
  - Built-in support for both offline development testing (mock mode) and online container verification (live mode).
  - Validated successfully by executing the script in the workspace.

### Step 2G: Prompts (`prompts/`)
- **System Prompt (`prompts/system/base.md`)**:
  - Wrote production-grade grounded-answer system prompt with `{{tenant_name}}` templating.
  - Added **No Meta-Commentary** rule (bot answers naturally, never says "based on the provided context").
  - Added **No System Leaking** rule to prevent prompt injection attacks from exposing instructions.
  - Defined explicit `Source 1: ... --- Source 2: ...` context format for runtime injection.
  - Standardized bracket citation style (e.g., `[Source 1]`).
- **Intent Classifier (`prompts/router/intent_classifier.md`)**:
  - Defined 6 intent categories: `greeting`, `faq`, `knowledge_search`, `lead_capture`, `escalation`, `off_topic`.
  - Added strict raw-JSON output constraint (no markdown code block wrapping).
  - Added 6 few-shot examples (one per intent) to guide classification accuracy.

### Unit Tests (`tests/test_mohammad_rag.py`)
- **Created Comprehensive Test Suite (36 tests)**:
  - **Chunking (7 tests)**: FAQ standard/single/fallback/empty, text splitting, metadata, document routing for all 4 content types.
  - **Reranking (6 tests)**: Deduplication, threshold filtering, max results cap, empty input, all-below-threshold, sort order.
  - **Embedding Client (4 tests)**: No-cache path, empty list, single-text helper, missing model raises RuntimeError.
  - **RAG Service (5 tests)**: index_document orchestration, empty chunk skip, delete_document_index, answer_from_knowledge with/without results.
  - **Content API Schemas (5 tests)**: Valid creation, invalid type rejection, missing field rejection, all valid types, response fields.
  - **Eval Golden Set (5 tests)**: Minimum 15 cases, required keys, unique IDs, non-empty keywords, content type coverage.
  - **Smart Skip Logic**: Tests requiring container-only deps (`fastapi`, `sqlalchemy`, `minio`) skip gracefully with `@unittest.skipUnless` instead of failing.
- **Results**: 29 passed, 7 skipped (container-only), 0 failures.

### Bug Fix: Chunking Infinite Loop
- **Fixed `_merge_pieces_with_overlap()` in `services/rag/chunking.py`**:
  - The overlap rollback loop could roll back to `i - 1`, causing `i` to never advance when `chunk_overlap=0`.
  - Changed the lower bound from `range(j-1, i-1, -1)` to `range(j-1, i, -1)` to guarantee forward progress on every iteration.

### API Dependencies
- Created `apps/api/requirements.txt` to track dependencies for the backend.
- Added `sentence-transformers`, a CPU-only build of `torch`, and `redis` to ensure the environment is fully equipped to run the embedding client.

## Phase 4: Router & Agent

### Step 4I: Verification (`tests/test_mohammad_verification_4i.py`)
- **4I.1 — Easy turns don't invoke the agent (6 tests)**: greeting → direct (agent_fn call count == 0); off_topic → direct (agent_fn not called); faq + knowledge_search with high-confidence RAG → rag path (agent_fn not called).
- **4I.2 — Hard turns invoke the agent (5 tests)**: knowledge_search with low RAG confidence falls through to agent; lead_capture intent → agent with `lead_captured` action; escalation intent → agent with `escalated` action; tool args verified on `capture_lead` and `escalate`.
- **4I.3 — Agent loop bounded (4 tests)**: LLM returning infinite tool calls stops at `MAX_ITERATIONS=5`; custom limit respected; loop exits immediately on first text reply; unapproved tool blocked without crash.
- **4I.4 — Tenant isolation (5 tests)**: `rag_search` and `capture_lead` always called with the requesting tenant's `tenant_id`; concurrent calls for different tenants don't mix IDs; `route()` passes `tenant_id` to RAG service.

### Step 4H: Agent Evals (`evals/agent/`)
- **Golden set (`evals/agent/golden_set.json`)**: 17 scenarios across 4 categories — easy turns (3 greeting, 3 faq, 1 off_topic), hard turns (5 knowledge_search), lead capture (2), escalation (3).
- **Eval script (`evals/agent/run_evals.py`)**: mock mode (deterministic, no LLM needed) and live mode (`OPENAI_API_KEY`). Metrics: correct routing %, correct tool selection %, loop completion %. Pass threshold: routing ≥ 85%.
- **Mock mode result**: 17/17 routing correct (100%), 10/10 tool selection (100%), 10/10 loop completion (100%) — PASSED.
- **Key insight captured in eval**: hard turns (scenario_type="hard") use low-confidence RAG mock (0.2) to trigger the RAG→agent fallback; easy turns use high-confidence (0.85) to stay in the RAG path.

### Step 4G: Classifier Contract (`services/router/classifier_contract.py`)
- **Typed contract module**: `ClassifyRequest`, `ClassifyResponse`, `ClassifyHealthResponse` dataclasses defining the `POST /classify` and `GET /health` API shared with Rayan.
- **`ClassifyResponse.is_valid()`**: rejects unknown intents and out-of-range confidence values.
- **`ClassifyHealthResponse.is_serving()`**: returns True only when both `model_loaded=True` AND `model_checksum_valid=True` (OPS-04 enforcement).
- **`verify_classifier_health(url)`**: async function that pings `GET /health` and returns a `ClassifyHealthResponse` or `None` if unreachable.
- **OPS-04 spec documented**: model server must compute SHA-256 of the artifact on startup, compare to `CLASSIFIER_MODEL_SHA256`, and return 503 on all `/classify` requests if the check fails.
- **`VALID_INTENTS` kept in sync**: test verifies `classifier_contract.VALID_INTENTS == router.INTENTS` so the two modules never diverge.

### Step 4E: Conversation Endpoints (`apps/api/app/api/v1/conversations.py`)
- **POST /message (4E.1)**:
  - Accepts `session_id` + `message` (validated: 1–4096 chars).
  - Loads conversation history from Redis (`conv:{tenant_id}:{session_id}`).
  - Calls `agent_service.process_message()` which routes through intent classification → direct / RAG / agent.
  - Saves updated history (user + assistant turns) back to Redis with 30-min TTL after every response, including direct-path replies (agent loop saves its own path internally).
  - Returns `{ reply, intent, action, sources, rag_confidence }`.
  - Returns HTTP 500 on processing failures; Redis/LLM absence degrades gracefully.
- **GET /{session_id} (4E.2)**:
  - Loads history from Redis scoped to `tenant_id`.
  - Strips system/tool messages — only `user` and `assistant` turns are returned to callers.
- **Clients**: Redis and OpenAI clients are lazily-initialized module-level singletons from env (`REDIS_URL`, `OPENAI_API_KEY`); `CLASSIFIER_URL` is forwarded to the router's model-server path.
- **Dependency**: Added `openai>=1.0.0` to `apps/api/requirements.txt`.

### Step 4D: Agent Service (`apps/api/app/services/agent_service.py`)
- **Wired the agent service (4D.1)**:
  - `process_message()` delegates entirely to `services.router.router.route()` + `services.agent.agent.run_agent()`.
  - Passes `tenant_id` through the entire chain (router → RAG/agent → tools).
  - Returns `{ reply, intent, action, sources, rag_confidence }` — `intent` added to expose classification result to the conversation endpoint.

### Step 4B: Bounded Agent Loop (`services/agent/agent.py` + `services/agent/tools.py`)
- **Implemented bounded agent loop (Steps 4B.1 + 4B.2)**:
  - `run_agent()` in `services/agent/agent.py` runs up to `MAX_ITERATIONS=5` rounds of tool calling.
  - Each iteration calls the LLM with `TOOL_DEFINITIONS`; if tool calls are returned they are dispatched to `execute_tool()` and results are appended; a text response ends the loop.
  - If `max_iterations` is reached without a final answer, returns a graceful handoff reply with `action="escalated"` (satisfies ROUT-07).
  - Unapproved tool names (anything outside `rag_search`, `capture_lead`, `escalate`) are blocked and logged at the point of dispatch (ROUT-04).
- **Implemented three agent tools (Step 4C)**:
  - `rag_search` — calls `services.rag.retrieval.retrieve` + `rerank`, injectable via `retrieval_fn` for tests.
  - `capture_lead` — validates name+email, inserts into `leads` table (gracefully skips if `db_session` is None).
  - `escalate` — marks conversation as escalated in `conversations` table (gracefully skips if `db_session` is None).
  - All three tools defined in OpenAI function-calling schema in `TOOL_DEFINITIONS`.
- **Implemented conversation memory (Step 4B.3)**:
  - `_load_memory()` reads `conv:{tenant_id}:{session_id}` from Redis and merges with provided history; degrades gracefully on Redis failure.
  - `_save_memory()` appends new user+assistant turns and persists with 30-minute TTL (`ex=1800`).
  - `_trim_history()` caps at 10 messages and 12 000 chars (~3 000 tokens), trimming oldest first.
- **Wrote agent tool-use prompt (`prompts/agent/tool_use.md`)**:
  - Defines the three allowed tools, behavioral rules (search-before-answer, lead consent, escalation trigger), tenant isolation, and no-system-leaking constraints.
- **Unit tests (`tests/test_mohammad_agent.py`)**: 30 tests, all passing.
  - Tool schema (5), `execute_tool` dispatcher (6), `_trim_history` (4), memory helpers (5), `run_agent` end-to-end (10).

### Step 4A: Intent Router (`services/router/router.py`)
- **Implemented classifier-based router (Step 4A.1)**:
  - `classify_intent()` tries Rayan's model server (`POST /classify`) first, then falls back to LLM with the `prompts/router/intent_classifier.md` prompt, then falls back to `knowledge_search` with 0.0 confidence.
  - `route()` dispatches to `"direct"` (greeting/off_topic), `"rag"` (faq/knowledge_search), or `"agent"` (lead_capture/escalation) based on intent and confidence.
  - Intent and route are surfaced in the returned `RouteResult` dataclass.
- **Implemented fallback logic (Step 4A.2)**:
  - Classifier confidence below `0.7` → always routes to agent.
  - RAG answer confidence below `0.5` → escalates to agent when `agent_fn` is wired.
  - When `agent_fn` is `None` (Phase 4B not yet done), returns a graceful handoff reply instead of crashing.
- **Implemented routing decision logging (Step 4A.3)**:
  - Every call logs: `tenant_id`, `session_id`, `msg_hash` (SHA-256[:16]), `intent`, `confidence`, `routed_to`, `classifier_source`.
- **Unit tests (`tests/test_mohammad_router.py`)**: 25 tests, all passing.
  - Decision logic (8 tests), classify fallback chain (5 tests), end-to-end `route()` paths (10 tests), log field format (2 tests).
- **Dependency**: Added `httpx>=0.25.0` to `apps/api/requirements.txt` for async HTTP calls to Rayan's model server.

## Phase 5: Production Hardening

### Step 5.1: SQL Schema Reconciliation
- **Fixed `services/rag/retrieval.py`**: Changed `FROM content_embeddings` → `FROM app.content_chunks` with explicit column aliases (`content AS chunk_text`, `document_id AS content_id`) to match Hanan's actual column names.
- **Fixed `apps/api/app/services/rag_service.py`**:
  - INSERT target changed to `app.content_chunks` with `document_id` (not `content_id`) and `content` (not `chunk_text`).
  - DELETE changed to `app.content_chunks` filtering on `document_id`.
  - LLM model corrected to `gpt-4.1-mini` (was the legacy `gpt-4-turbo`).
- **Fixed `apps/api/app/api/v1/content.py`**: All four SQL statements (`INSERT`, `SELECT` check, `UPDATE`, `DELETE`, `LIST`) now target `app.content_documents` with correct column names: `document_id` (was `id`), `content` (was `body`), `kind` (was `content_type`). `SELECT ... AS` aliases project back to the Pydantic response field names so the API contract is unchanged.
- **Migration `infrastructure/postgres/migrations/0003_embeddings.sql`** (Step 5.2):
  - Extends `content_documents_kind_check` constraint to accept `doc` and `service` (Mohammad's additional types).
  - Creates HNSW vector index on `app.content_chunks(embedding vector_cosine_ops)` with `m=16, ef_construction=64`.
  - Creates composite B-tree index on `(tenant_id, chunk_index)` for tenant-scoped scan optimisation.
  - Creates `app.content_embeddings` compatibility view mapping Hanan's column names (`chunk_id`, `document_id`, `content`) to Mohammad's aliases (`id`, `content_id`, `chunk_text`).

### Step 5.3: OpenTelemetry Tracing (`services/tracing.py`)
- **Created `services/tracing.py`**: Shared span helper with conditional OpenTelemetry import — works with or without `opentelemetry` installed (falls back to a `_NoopSpan`).
- **`router.classify` span** added to `services/router/router.py`: wraps `classify_intent()`, records `intent`, `confidence`, `source` attributes.
- **`rag.retrieve` span** added to `services/rag/retrieval.py`: wraps the pgvector DB execution, records `result_count`.
- **`rag.answer` span** added to `apps/api/app/services/rag_service.py`: wraps the full retrieval→rerank→LLM pipeline, records `reranked_count`.
- **`agent.loop` span** added to `services/agent/agent.py`: wraps the entire bounded tool-calling loop, records `iterations`.
- **`agent.tool_call` span** added for every approved tool dispatch inside the loop, records `tool` name.
- All spans carry `tenant_id` as a mandatory attribute for multi-tenant tracing isolation.

### Step 5.4: Right-to-Erasure (`apps/api/app/services/erasure_service.py`)
- **Created `apps/api/app/services/erasure_service.py`**: GDPR Article 17 compliant `purge_tenant()` function.
  - **pgvector**: `DELETE FROM app.content_chunks WHERE tenant_id = :tenant_id` — removes all embeddings and chunk text.
  - **Redis**: SCAN + DEL on pattern `conv:{tenant_id}:*` — removes all conversation-memory keys for the tenant.
  - **MinIO**: lists all objects under `{tenant_id}/` prefix and removes each — clears all raw content files.
  - Returns a summary dict with `chunks_deleted`, `redis_deleted`, `minio_deleted`, `errors`.
  - Fully idempotent — safe to call multiple times.
  - Gracefully skips each layer if the corresponding client is `None` (logs a warning instead of crashing).

---
*Last updated: 2026-05-26*
