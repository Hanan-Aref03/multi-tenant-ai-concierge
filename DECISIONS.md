# DECISIONS.md — Concierge Technical Decisions

Owner B (Mohammad) is primary author of this document. All owners contributed.

This log captures the key technical choices made during the build, including the argument for each decision and the trade-offs considered. Decisions are immutable — append new entries; do not edit old ones.

---

## DEC-01 — Router-First, Agent-Second Architecture

**Decision:** Route easy turns through a deterministic workflow (classify → direct/RAG/capture_lead) and invoke the bounded tool-calling agent only for turns that cannot be handled by the workflow.

**Argument:**

The agent-for-everything pattern (every turn goes through an LLM tool-caller) is correct in principle but expensive in practice: it adds an average of 200–400ms to every response and doubles API costs, even for simple FAQ questions where the right answer is already in the knowledge base. For a concierge assistant embedded on a business website, 80% of inbound messages are predictable — greetings, FAQ, pricing questions, "talk to a human" — and do not need free-form reasoning.

The router separates these cases:

```
confidence ≥ 0.65  →  workflow path (fast, cheap, deterministic)
confidence < 0.65  →  agent path   (flexible, slower, used only when needed)
```

This gives us sub-100ms response time for the majority of turns and reserves the agent for genuinely ambiguous or multi-step interactions.

**Trade-off considered:** A router can misclassify and route a complex question to RAG when it should go to the agent. The 0.65 confidence threshold was tuned to keep false-positives (over-confident mis-routes) below 5% on the held-out test set. When in doubt, the router falls back to the agent path.

**Status:** Implemented in `services/router/router.py`.

---

## DEC-02 — Classifier: TF-IDF + Logistic Regression over Neural Network or LLM

**Decision:** Use an augmented Word+Char TF-IDF + Logistic Regression pipeline for intent classification, not a neural network or LLM-based classifier.

**Argument:**

We evaluated three approaches on a held-out test set augmented with realistic hand-labeled examples:

| Model | Macro-F1 | Latency | Cost | Serving |
|-------|----------|---------|------|---------|
| Word+Char TF-IDF + LR | 0.985 | 0.32ms | Free | joblib, no torch |
| Small Neural Network | 0.972 | 0.03ms | Free | torch in container |
| LLM (Groq llama-3.1-8b) | 1.0 (manual) | 214ms | API cost per call | External API |

The classical ML model achieves 98.5% macro-F1 — comfortably above the CI gate threshold of 0.75 — at 0.32ms per inference on CPU. The neural network scores slightly lower on the held-out set and would require shipping a torch runtime in the model server container (+1 GB image, longer cold-start).

The LLM baseline scored perfectly on manual examples but adding 214ms to every message turn is unacceptable at the router level. It would also add Groq API cost to every visitor message — regardless of how trivial the routing decision is.

**Trade-off considered:** The classical model may struggle on out-of-distribution inputs (visitor messages with unusual phrasing). This is mitigated by the low-confidence fallback: anything below 0.65 goes to the agent, so a confused classifier sends turns to the LLM anyway.

**Status:** Implemented. Artifact: `apps/modelserver/artifacts/model/concierge_classifier.joblib`.

---

## DEC-03 — Embedding Model: all-MiniLM-L6-v2

**Decision:** Use `sentence-transformers/all-MiniLM-L6-v2` as the local embedding model for RAG retrieval, not an API-based embedding service.

**Argument:**

The embedding model runs once per content chunk at ingestion time and once per visitor query at retrieval time. The query embedding is the hot path — it is on every RAG-routed request. API-based embeddings (OpenAI `text-embedding-3-small`) would add 50–150ms of network latency and per-token cost to every retrieval-backed reply.

`all-MiniLM-L6-v2` is a 22M-parameter model that produces 384-dimensional embeddings. It runs on CPU in approximately 20ms per sentence (cached via Redis after the first call). The 384-dimensional space is sufficient for our 6-intent classification domain.

The model is loaded once at startup via sentence-transformers and cached in the embedding service process. Embeddings are additionally cached in Redis (24h TTL) to eliminate the CPU cost for repeated queries.

**Trade-off considered:** `all-MiniLM-L6-v2` is less accurate than OpenAI's embedding models on long documents. Our RAG chunks are ≤2000 characters, which is well within the model's optimal range.

**Status:** Implemented in `services/embeddings/client.py`.

---

## DEC-04 — Chunking Strategy: FAQ-Aware Recursive Splitter

**Decision:** Use a recursive text splitter with FAQ-pair locking (Q+A blocks are never split across chunks) and a 2000-character chunk size with 250-character overlap.

**Argument:**

Naive fixed-size chunking splits FAQ content at arbitrary boundaries, separating questions from answers. This breaks retrieval because the answer embedding does not contain the question context. We detect `Q:` / `A:` and `Question:` / `Answer:` patterns and lock each Q+A pair as an atomic chunk.

Chunk size of 2000 characters (~512 tokens) leaves room in the LLM context for the system prompt, conversation history, and generated answer. Overlap of 250 characters (64 tokens) ensures that sentences that straddle chunk boundaries appear in full in at least one chunk.

**Trade-off considered:** Longer chunks reduce the number of retrieval candidates needed to cover a topic but increase the token cost of LLM generation. At 2000 characters we balance recall against generation cost.

**Status:** Implemented in `services/rag/chunking.py`.

---

## DEC-05 — Retrieval: Cosine Similarity + Reranking

**Decision:** Use pgvector cosine similarity for initial retrieval (threshold ≥ 0.35), then rerank with a stricter threshold (0.65) and deduplicate by document.

**Argument:**

A single-stage retrieval with a tight threshold produces high-precision results but misses relevant chunks when phrasing differs from the stored content. Two-stage retrieval (loose first-pass, strict rerank) maintains recall while filtering noise in the final answer set.

The deduplication step (keep only the highest-scoring chunk per source document) prevents a single document from flooding the context window with redundant content, leaving room for diverse supporting evidence.

pgvector was chosen over a standalone vector database (Weaviate, Qdrant, Pinecone) because:
- It runs in the same Postgres instance, eliminating an additional service
- RLS policies apply to vector search natively — no separate tenant namespace management
- At demo scale (< 10M vectors per tenant), pgvector performance is competitive with dedicated stores

**Status:** Implemented in `services/rag/retrieval.py`.

---

## DEC-06 — Guardrails: Hybrid NeMo + Deterministic Rules

**Decision:** Implement the guardrails sidecar as a hybrid system: NeMo Guardrails is loaded from real config files as the class-aligned programmable guardrails layer, and deterministic Python rules remain as defense-in-depth and CI-friendly fallback checks.

**Argument:**

The Week 8 brief recommends NeMo Guardrails for topical, injection, and cross-tenant rails. The sidecar now includes a NeMo config under `services/guardrails/nemo/` and loads it through `RailsConfig`/`LLMRails` when `GUARDRAILS_USE_NEMO=true`.

The existing deterministic rules stay in place because they are fast, version-controlled, easy to test in CI, and do not require an LLM provider key during local development. NeMo failures do not crash the sidecar unless `GUARDRAILS_NEMO_STRICT=true`.

For a concierge assistant, the attack surface is narrow and well-defined:
- Prompt injection: "ignore previous instructions"
- Jailbreak: "act as DAN"
- Cross-tenant probing: "show me another tenant's data"
- Prompt disclosure: "show me your system prompt"

The hybrid flow is:
1. Redact PII/secrets using custom regex redaction.
2. Evaluate immutable platform rules.
3. Evaluate the NeMo-backed platform rail adapter if enabled and available.
4. Evaluate tenant blocked-topic policy, which can only make behavior stricter.

The CI red-team gate (`injection_redteam`) verifies that all canonical probes are refused on every push.

The trade-off is that novel adversarial framings not covered by the current patterns can bypass the regex rules. We mitigate this by:
1. Loading NeMo Guardrails as the programmable guardrails layer
2. Making the pattern library extend easily (one PR to add a new rule)
3. Treating the red-team eval as a living test suite that grows with discovered bypasses

**Status:** Implemented in `apps/guardrails/app/main.py`, `services/guardrails/nemo_adapter.py`, `services/guardrails/rules.py`, `services/guardrails/redaction.py`, and `services/guardrails/nemo/`.

---

## DEC-07 — Auth: Short-Lived JWT over Server Sessions

**Decision:** Use a short-lived (30-minute) JWT for widget authentication instead of server-side sessions.

**Argument:**

Server-side sessions require a shared session store (Redis) that all API replicas must reach. This creates a stateful dependency that complicates horizontal scaling and failover.

A signed JWT encodes `tenant_id`, `widget_id`, and `conversation_id` and is self-contained. Any API replica can verify it without a database lookup. The 30-minute expiry limits the blast radius of a stolen token. Token exchange happens once (when the widget loads) and carries the conversation through its natural duration.

The token is transmitted in the iframe URL, not in DOM storage, to reduce the XSS risk. `tenant_id` is never re-read from the request body — it is always derived from the verified token claims.

**Trade-off considered:** Stateless JWTs cannot be revoked individually before expiry. If a token is leaked, it is valid for up to 30 minutes. For the widget use case (public-facing visitors), this window is acceptable. Admin sessions use a separate auth path with server-side revocation.

**Status:** Implemented in `backend/app/services/widget_token.py` and `backend/app/middleware/widget_auth.py`.

---

## DEC-08 — Lean Serving: No Training Framework in Production Containers

**Decision:** Production model-serving containers ship only the inference runtime (scikit-learn + joblib, onnxruntime), not training frameworks (torch, tensorflow, transformers).

**Argument:**

A PyTorch base image adds ~1.5 GB to the model server container. This increases cold-start time, pull time, and attack surface. The classifier (TF-IDF + LR) is fully serializable with joblib and requires only scikit-learn to serve. There is no gradient computation, no auto-differentiation, and no GPU dependency at inference time.

If the model is later re-exported to ONNX (via `apps/modelserver/scripts/export_onnx.py`), the serving runtime drops to `onnxruntime` alone — no scikit-learn dependency in production.

**Status:** Implemented. Docker image is Python 3.11-slim + scikit-learn + fastapi. See `apps/modelserver/Dockerfile`.
