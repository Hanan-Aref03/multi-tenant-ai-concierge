"""Comprehensive tests for Mohammad's RAG pipeline components.

Covers:
- Chunking (FAQ + recursive text splitter)
- Retrieval reranking & deduplication
- Embedding client (cache miss path)
- RAG service (index_document, delete_document_index, answer_from_knowledge)
- Content API Pydantic schema validation
- Eval golden set integrity
"""

import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from services.rag.chunking import chunk_faq, chunk_text, process_document, Chunk
from services.rag.retrieval import rerank, RetrievalResult
from services.embeddings.client import EmbeddingClient

# Check for container-only dependencies
try:
    import sqlalchemy
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

try:
    import fastapi
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Helper to run async tests
# ---------------------------------------------------------------------------
def run_async(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===================================================================
# 1. Chunking Tests
# ===================================================================
class TestChunkFAQ(unittest.TestCase):
    """Tests for FAQ-specific chunking."""

    def test_standard_two_pairs(self):
        faq_text = (
            "Question: What is your name?\n"
            "Answer: I am a customer assistant bot.\n\n"
            "Q: Where are you located?\n"
            "A: We are online-only.\n"
        )
        chunks = chunk_faq(faq_text, tenant_id="t1", content_id="d1")
        self.assertEqual(len(chunks), 2)
        self.assertIn("What is your name?", chunks[0].text)
        self.assertIn("Where are you located?", chunks[1].text)
        for c in chunks:
            self.assertEqual(c.metadata["content_type"], "faq")
            self.assertEqual(c.metadata["tenant_id"], "t1")

    def test_single_pair(self):
        faq_text = "Q: How do I reset my password?\nA: Click the forgot password link."
        chunks = chunk_faq(faq_text, tenant_id="t1", content_id="d2")
        self.assertEqual(len(chunks), 1)

    def test_fallback_on_plain_text(self):
        plain = "This has no FAQ delimiters at all."
        chunks = chunk_faq(plain, tenant_id="t1", content_id="d3")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, plain)

    def test_empty_input(self):
        chunks = chunk_faq("", tenant_id="t1", content_id="d4")
        # Should return empty or a single empty-ish chunk
        self.assertTrue(len(chunks) <= 1)


class TestChunkText(unittest.TestCase):
    """Tests for the recursive character text splitter."""

    def test_paragraph_splitting(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_text(text, "t1", "d1", "doc", chunk_size=20, chunk_overlap=0)
        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0].text.strip(), "Para one.")

    def test_single_short_text_no_split(self):
        text = "Short text."
        chunks = chunk_text(text, "t1", "d1", "doc", chunk_size=2000, chunk_overlap=200)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Short text.")

    def test_metadata_populated(self):
        chunks = chunk_text("Hello world", "t1", "d1", "policy")
        self.assertEqual(chunks[0].metadata["tenant_id"], "t1")
        self.assertEqual(chunks[0].metadata["content_id"], "d1")
        self.assertEqual(chunks[0].metadata["content_type"], "policy")


class TestProcessDocument(unittest.TestCase):
    """Tests for the top-level routing function."""

    def test_faq_routing(self):
        chunks = process_document("Q: What?\nA: Yes.", "t1", "d1", "faq")
        self.assertEqual(chunks[0].metadata["content_type"], "faq")

    def test_doc_routing(self):
        chunks = process_document("General text.", "t1", "d2", "doc")
        self.assertEqual(chunks[0].metadata["content_type"], "doc")

    def test_policy_routing(self):
        chunks = process_document("Policy text.", "t1", "d3", "policy")
        self.assertEqual(chunks[0].metadata["content_type"], "policy")

    def test_service_routing(self):
        chunks = process_document("Service info.", "t1", "d4", "service")
        self.assertEqual(chunks[0].metadata["content_type"], "service")


# ===================================================================
# 2. Retrieval & Reranking Tests
# ===================================================================
class TestRerank(unittest.TestCase):
    """Tests for the reranking / dedup / threshold logic."""

    def test_deduplication_keeps_highest(self):
        results = [
            RetrievalResult("Chunk A", 0.90, "doc_1", 0, {}),
            RetrievalResult("Chunk B", 0.95, "doc_1", 1, {}),
            RetrievalResult("Chunk C", 0.80, "doc_2", 0, {}),
        ]
        reranked = rerank(results, max_results=5, score_threshold=0.50)
        self.assertEqual(len(reranked), 2)
        self.assertEqual(reranked[0].content_id, "doc_1")
        self.assertEqual(reranked[0].score, 0.95)
        self.assertEqual(reranked[1].content_id, "doc_2")

    def test_threshold_filters_low_scores(self):
        results = [
            RetrievalResult("High", 0.80, "doc_1", 0, {}),
            RetrievalResult("Low", 0.50, "doc_2", 0, {}),
        ]
        reranked = rerank(results, max_results=5, score_threshold=0.65)
        self.assertEqual(len(reranked), 1)
        self.assertEqual(reranked[0].content_id, "doc_1")

    def test_max_results_cap(self):
        results = [
            RetrievalResult(f"Chunk {i}", 0.90 - i * 0.01, f"doc_{i}", 0, {})
            for i in range(10)
        ]
        reranked = rerank(results, max_results=3, score_threshold=0.50)
        self.assertEqual(len(reranked), 3)

    def test_empty_input(self):
        reranked = rerank([], max_results=3, score_threshold=0.65)
        self.assertEqual(len(reranked), 0)

    def test_all_below_threshold(self):
        results = [
            RetrievalResult("Low 1", 0.30, "doc_1", 0, {}),
            RetrievalResult("Low 2", 0.20, "doc_2", 0, {}),
        ]
        reranked = rerank(results, max_results=5, score_threshold=0.65)
        self.assertEqual(len(reranked), 0)

    def test_sorted_descending(self):
        results = [
            RetrievalResult("A", 0.70, "doc_a", 0, {}),
            RetrievalResult("B", 0.90, "doc_b", 0, {}),
            RetrievalResult("C", 0.80, "doc_c", 0, {}),
        ]
        reranked = rerank(results, max_results=5, score_threshold=0.50)
        scores = [r.score for r in reranked]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ===================================================================
# 3. Embedding Client Tests
# ===================================================================
class TestEmbeddingClient(unittest.TestCase):
    """Tests for the embedding client with mocked model."""

    @patch("services.embeddings.client.SentenceTransformer")
    def test_embed_texts_no_cache(self, mock_transformer):
        mock_model = MagicMock()
        mock_encode_result = MagicMock()
        mock_encode_result.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_encode_result
        mock_transformer.return_value = mock_model

        client = EmbeddingClient()
        client.model = mock_model

        embeddings = run_async(client.embed_texts("t1", ["test text"], redis_client=None))
        self.assertEqual(len(embeddings), 1)
        self.assertEqual(embeddings[0], [0.1, 0.2, 0.3])

    @patch("services.embeddings.client.SentenceTransformer")
    def test_embed_texts_empty_list(self, mock_transformer):
        client = EmbeddingClient()
        client.model = MagicMock()
        embeddings = run_async(client.embed_texts("t1", [], redis_client=None))
        self.assertEqual(embeddings, [])

    @patch("services.embeddings.client.SentenceTransformer")
    def test_embed_text_single_helper(self, mock_transformer):
        mock_model = MagicMock()
        mock_encode_result = MagicMock()
        mock_encode_result.tolist.return_value = [[0.4, 0.5, 0.6]]
        mock_model.encode.return_value = mock_encode_result
        mock_transformer.return_value = mock_model

        client = EmbeddingClient()
        client.model = mock_model

        embedding = run_async(client.embed_text("t1", "single text", redis_client=None))
        self.assertEqual(embedding, [0.4, 0.5, 0.6])

    def test_no_model_raises(self):
        client = EmbeddingClient()
        client.model = None
        with self.assertRaises(RuntimeError):
            run_async(client.embed_texts("t1", ["text"], redis_client=None))


# ===================================================================
# 4. RAG Service Tests (mocked DB & embeddings)
# ===================================================================
class TestRAGService(unittest.TestCase):
    """Tests for rag_service.py functions with mocked dependencies."""

    @unittest.skipUnless(HAS_SQLALCHEMY, "sqlalchemy not installed locally")
    @patch("apps.api.app.services.rag_service.get_embedding_client")
    @patch("apps.api.app.services.rag_service.process_document")
    def test_index_document_calls_embed_and_insert(self, mock_process, mock_get_client):
        from apps.api.app.services.rag_service import index_document

        # Setup mocks
        mock_process.return_value = [
            Chunk(text="chunk 1", metadata={"tenant_id": "t1", "content_id": "d1", "content_type": "doc"}),
            Chunk(text="chunk 2", metadata={"tenant_id": "t1", "content_id": "d1", "content_type": "doc"}),
        ]
        mock_client = MagicMock()
        mock_client.embed_texts = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        mock_get_client.return_value = mock_client

        mock_db = AsyncMock()

        run_async(index_document("t1", "d1", "Title", "body text", "doc", mock_db))

        # Verify embed was called with the 2 chunk texts
        mock_client.embed_texts.assert_awaited_once_with("t1", ["chunk 1", "chunk 2"], None)
        # Verify DB inserts happened (delete + 2 inserts)
        self.assertTrue(mock_db.execute.await_count >= 2)

    @patch("apps.api.app.services.rag_service.get_embedding_client")
    @patch("apps.api.app.services.rag_service.process_document")
    def test_index_document_skips_empty_chunks(self, mock_process, mock_get_client):
        from apps.api.app.services.rag_service import index_document

        mock_process.return_value = []  # No chunks generated
        mock_db = AsyncMock()

        # Should return without calling embed or DB
        run_async(index_document("t1", "d1", "Title", "", "doc", mock_db))
        mock_get_client.assert_not_called()

    @unittest.skipUnless(HAS_SQLALCHEMY, "sqlalchemy not installed locally")
    def test_delete_document_index(self):
        from apps.api.app.services.rag_service import delete_document_index

        mock_db = AsyncMock()
        run_async(delete_document_index("t1", "d1", mock_db))
        mock_db.execute.assert_awaited_once()

    @patch("apps.api.app.services.rag_service.rerank")
    @patch("apps.api.app.services.rag_service.retrieve")
    def test_answer_from_knowledge_no_results(self, mock_retrieve, mock_rerank):
        from apps.api.app.services.rag_service import answer_from_knowledge

        mock_retrieve.return_value = []
        mock_rerank.return_value = []

        mock_db = AsyncMock()
        result = run_async(answer_from_knowledge("t1", "What is X?", mock_db))

        self.assertEqual(result["sources"], [])
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("couldn't find", result["answer"])

    @patch("apps.api.app.services.rag_service.rerank")
    @patch("apps.api.app.services.rag_service.retrieve")
    def test_answer_from_knowledge_with_results(self, mock_retrieve, mock_rerank):
        from apps.api.app.services.rag_service import answer_from_knowledge

        mock_retrieve.return_value = [
            RetrievalResult("Answer text", 0.85, "doc_1", 0, {}),
        ]
        mock_rerank.return_value = [
            RetrievalResult("Answer text", 0.85, "doc_1", 0, {}),
        ]

        mock_db = AsyncMock()
        result = run_async(answer_from_knowledge("t1", "What is X?", mock_db))

        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["content_id"], "doc_1")
        self.assertAlmostEqual(result["confidence"], 0.85)


# ===================================================================
# 5. Content API Schema Tests
# ===================================================================
@unittest.skipUnless(HAS_FASTAPI and HAS_SQLALCHEMY, "fastapi/sqlalchemy/minio not installed locally")
class TestContentSchemas(unittest.TestCase):
    """Tests for the Pydantic request/response schemas."""

    def test_content_create_valid(self):
        from apps.api.app.api.v1.content import ContentCreate
        obj = ContentCreate(title="FAQ", body="Q: What?\nA: Yes.", content_type="faq")
        self.assertEqual(obj.title, "FAQ")
        self.assertEqual(obj.content_type, "faq")

    def test_content_create_invalid_type(self):
        from apps.api.app.api.v1.content import ContentCreate
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ContentCreate(title="Bad", body="text", content_type="invalid_type")

    def test_content_create_missing_title(self):
        from apps.api.app.api.v1.content import ContentCreate
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ContentCreate(body="text", content_type="doc")

    def test_content_create_all_valid_types(self):
        from apps.api.app.api.v1.content import ContentCreate
        for ct in ["faq", "doc", "policy", "service"]:
            obj = ContentCreate(title="T", body="B", content_type=ct)
            self.assertEqual(obj.content_type, ct)

    def test_content_response_fields(self):
        from apps.api.app.api.v1.content import ContentResponse
        obj = ContentResponse(id="abc", tenant_id="t1", title="T", body="B", content_type="doc")
        self.assertEqual(obj.id, "abc")
        self.assertEqual(obj.tenant_id, "t1")


# ===================================================================
# 6. Eval Golden Set Integrity
# ===================================================================
class TestEvalGoldenSet(unittest.TestCase):
    """Validate the eval golden set structure and completeness."""

    @classmethod
    def setUpClass(cls):
        golden_path = os.path.join(
            os.path.dirname(__file__), "..", "evals", "rag", "golden_set.json"
        )
        with open(golden_path, "r") as f:
            cls.golden_set = json.load(f)

    def test_minimum_15_cases(self):
        self.assertGreaterEqual(len(self.golden_set), 15)

    def test_required_keys(self):
        required = {"id", "query", "expected_content_id", "expected_keywords", "content_type"}
        for case in self.golden_set:
            self.assertTrue(required.issubset(case.keys()), f"Missing keys in {case.get('id')}")

    def test_unique_ids(self):
        ids = [c["id"] for c in self.golden_set]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate IDs found in golden set")

    def test_keywords_not_empty(self):
        for case in self.golden_set:
            self.assertGreater(len(case["expected_keywords"]), 0, f"Empty keywords for {case['id']}")

    def test_content_types_coverage(self):
        types = {c["content_type"] for c in self.golden_set}
        self.assertIn("faq", types)
        self.assertIn("doc", types)
        self.assertIn("policy", types)
        self.assertIn("service", types)


if __name__ == "__main__":
    unittest.main()
