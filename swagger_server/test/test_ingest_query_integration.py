# coding: utf-8
"""
Integration tests for /ingest and /query endpoints.
Uses mocked embedder/LLM and in-memory ChromaDB to avoid real downloads/API calls.
"""

from __future__ import absolute_import

import json
from unittest import mock

import chromadb

from swagger_server.test import BaseTestCase


class FakeVectors:
    """Mock return from sentence_transformers.encode() for testing."""

    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class TestIngestQueryIntegration(BaseTestCase):
    """Integration tests for document ingestion and querying."""

    def setUp(self):
        """Set up test fixtures: in-memory Chroma and mocked embedder."""
        super().setUp()

        self.in_memory_client = chromadb.EphemeralClient()

        self.mock_embedder_patcher = mock.patch(
            "swagger_server.services.embedder.embed"
        )
        self.mock_embedder = self.mock_embedder_patcher.start()

        self.mock_vector_store_patcher = mock.patch(
            "swagger_server.services.vector_store.get_store"
        )
        self.mock_get_store = self.mock_vector_store_patcher.start()

        self.mock_llm_patcher = mock.patch(
            "swagger_server.services.llm.generate_answer"
        )
        self.mock_llm = self.mock_llm_patcher.start()

    def tearDown(self):
        """Clean up mocks."""
        self.mock_embedder_patcher.stop()
        self.mock_vector_store_patcher.stop()
        self.mock_llm_patcher.stop()
        super().tearDown()

    def _setup_store_and_embedder(self):
        """Configure mocks for a test run: in-memory Chroma + deterministic embeddings."""
        collection = self.in_memory_client.get_or_create_collection(
            name="default"
        )

        def mock_embed(texts):
            return [[float(i) / len(text) for i in range(3)] for text in texts]

        self.mock_embedder.side_effect = mock_embed

        def mock_get_store_impl(collection_name="default"):
            from swagger_server.services.vector_store import VectorStore

            store = mock.Mock(spec=VectorStore)
            store.collection_name = collection_name
            store._collection = collection

            def add_docs(chunks, embeddings):
                ids = [f"id_{i}" for i in range(len(chunks))]
                documents = [c["text"] for c in chunks]
                metadatas = [
                    {
                        "source": c.get("source", "unknown"),
                        "page": c.get("page"),
                        "chunk_index": c.get("chunk_index"),
                        "ingested_at": "2026-01-01T00:00:00Z",
                    }
                    for c in chunks
                ]
                collection.add(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                return len(documents)

            def query_impl(embedding, top_k):
                result = collection.query(
                    query_embeddings=[embedding],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"],
                )
                rows = []
                for i, doc in enumerate(result.get("documents", [[]])[0]):
                    metadata = result.get("metadatas", [[]])[0][i] if i < len(
                        result.get("metadatas", [[]])[0]
                    ) else {}
                    score = 0.9 - (i * 0.1)
                    rows.append(
                        {
                            "text": doc,
                            "source": metadata.get("source"),
                            "page": metadata.get("page"),
                            "chunk_index": metadata.get("chunk_index"),
                            "score": score,
                        }
                    )
                return rows

            store.add_documents = add_docs
            store.query = query_impl
            store.get_collection_info = lambda: {
                "total_chunks": collection.count(),
                "sources": {"test_doc.txt": collection.count()},
            }
            return store

        self.mock_get_store.side_effect = mock_get_store_impl

    def test_ingest_json_text_returns_chunk_count_and_metadata(self):
        """Ingest JSON text and verify chunk count and metadata."""
        self._setup_store_and_embedder()

        body = {
            "text": "First sentence. Second sentence. Third sentence.",
            "source": "test_doc.txt",
            "collection_name": "default",
        }

        response = self.client.open(
            "/ingest",
            method="POST",
            data=json.dumps(body),
            content_type="application/json",
        )

        self.assert200(response)
        data = json.loads(response.data.decode("utf-8"))
        assert data["chunk_count"] > 0
        assert data["source"] == "test_doc.txt"
        assert data["collection_name"] == "default"
        assert "ingested_at" in data

    def test_ingest_then_query_returns_answer_with_sources(self):
        """Full pipeline: ingest text, then query and verify answer with sources."""
        self._setup_store_and_embedder()

        doc_body = {
            "text": "The capital of France is Paris. Paris is known for the Eiffel Tower.",
            "source": "geography.txt",
            "collection_name": "default",
        }

        ingest_response = self.client.open(
            "/ingest",
            method="POST",
            data=json.dumps(doc_body),
            content_type="application/json",
        )
        self.assert200(ingest_response)

        self.mock_llm.return_value = {
            "answer": "The capital of France is Paris. [1]",
            "sources": [
                {
                    "text": "The capital of France is Paris.",
                    "source": "geography.txt",
                    "page": None,
                    "chunk_index": 0,
                    "score": 0.95,
                }
            ],
            "model_used": "gpt-4o-mini",
        }

        query_body = {
            "question": "What is the capital of France?",
            "top_k": 4,
            "collection_name": "default",
        }

        query_response = self.client.open(
            "/query",
            method="POST",
            data=json.dumps(query_body),
            content_type="application/json",
        )
        self.assert200(query_response)

        data = json.loads(query_response.data.decode("utf-8"))
        assert "answer" in data
        assert "Paris" in data["answer"]
        assert "sources" in data
        assert len(data["sources"]) > 0
        assert data["sources"][0]["source"] == "geography.txt"

    def test_query_without_text_returns_validation_error(self):
        """Query with empty question returns 400."""
        self._setup_store_and_embedder()

        body = {"question": "", "top_k": 4, "collection_name": "default"}

        response = self.client.open(
            "/query",
            method="POST",
            data=json.dumps(body),
            content_type="application/json",
        )

        self.assert400(response)
        data = json.loads(response.data.decode("utf-8"))
        assert data["error"] == "validation_error"

    def test_ingest_without_text_or_file_returns_validation_error(self):
        """Ingest with missing text returns 400."""
        self._setup_store_and_embedder()

        body = {"text": "", "source": "doc.txt", "collection_name": "default"}

        response = self.client.open(
            "/ingest",
            method="POST",
            data=json.dumps(body),
            content_type="application/json",
        )

        self.assert400(response)
        data = json.loads(response.data.decode("utf-8"))
        assert data["error"] == "validation_error"


if __name__ == "__main__":
    import unittest

    unittest.main()
