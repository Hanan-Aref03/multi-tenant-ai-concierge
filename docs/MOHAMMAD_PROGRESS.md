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

---
*Last updated: 2026-05-25*
