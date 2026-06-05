import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings


class VectorStore:
	"""Small wrapper around ChromaDB for document chunk storage and retrieval."""

	def __init__(
		self,
		collection_name: str = "default",
		persist_directory: str = "./chroma_db/",
	) -> None:
		self.collection_name = collection_name
		self.persist_directory = persist_directory

		chroma_host = os.getenv("CHROMA_HOST", "").strip()
		if chroma_host:
			chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
			chroma_ssl = os.getenv("CHROMA_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}
			self._client = chromadb.HttpClient(
				host=chroma_host,
				port=chroma_port,
				ssl=chroma_ssl,
				settings=Settings(anonymized_telemetry=False),
			)
		else:
			os.makedirs(self.persist_directory, exist_ok=True)
			self._client = chromadb.PersistentClient(
				path=self.persist_directory,
				settings=Settings(anonymized_telemetry=False),
			)
		self._collection = self._client.get_or_create_collection(name=self.collection_name)

	def add_documents(
		self,
		chunks: List[Dict[str, Any]],
		embeddings: List[List[float]],
	) -> int:
		"""Add chunk documents with precomputed embeddings."""
		if len(chunks) != len(embeddings):
			raise ValueError("chunks and embeddings must have the same length")
		if not chunks:
			return 0

		ids: List[str] = []
		documents: List[str] = []
		metadatas: List[Dict[str, Any]] = []
		now = datetime.now(timezone.utc).isoformat()

		for index, chunk in enumerate(chunks):
			text = str(chunk.get("text", "")).strip()
			if not text:
				continue

			ids.append(str(chunk.get("id") or uuid4()))
			documents.append(text)
			metadatas.append(
				{
					"source": str(chunk.get("source", "unknown")),
					"page": chunk.get("page"),
					"chunk_index": chunk.get("chunk_index", index),
					"ingested_at": now,
				}
			)

		if not documents:
			return 0

		filtered_embeddings = [
			embeddings[i]
			for i, chunk in enumerate(chunks)
			if str(chunk.get("text", "")).strip()
		]

		self._collection.add(
			ids=ids,
			documents=documents,
			embeddings=filtered_embeddings,
			metadatas=metadatas,
		)
		return len(documents)

	def query(self, embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
		"""Query top-k nearest chunks for a single embedding vector."""
		if top_k <= 0:
			raise ValueError("top_k must be > 0")

		result = self._collection.query(
			query_embeddings=[embedding],
			n_results=top_k,
			include=["documents", "metadatas", "distances"],
		)

		documents = result.get("documents", [[]])[0]
		metadatas = result.get("metadatas", [[]])[0]
		distances = result.get("distances", [[]])[0]

		rows: List[Dict[str, Any]] = []
		for i, doc in enumerate(documents):
			metadata = metadatas[i] if i < len(metadatas) else {}
			distance = distances[i] if i < len(distances) else None
			score = None
			if distance is not None:
				# Chroma distance is lower-is-better; return a similarity-like score as well.
				score = 1.0 - float(distance)

			rows.append(
				{
					"text": doc,
					"source": metadata.get("source"),
					"page": metadata.get("page"),
					"chunk_index": metadata.get("chunk_index"),
					"score": score,
					"distance": distance,
				}
			)

		return rows

	def get_collection_info(self) -> Dict[str, Any]:
		"""Return basic collection metadata and chunk counts."""
		count = self._collection.count()
		peek_size = min(count, 1000)
		peek = self._collection.peek(limit=peek_size) if count else {}
		metadatas = peek.get("metadatas", []) if peek else []

		per_source: Dict[str, int] = {}
		for metadata in metadatas:
			source = str((metadata or {}).get("source", "unknown"))
			per_source[source] = per_source.get(source, 0) + 1

		return {
			"collection_name": self.collection_name,
			"persist_directory": self.persist_directory,
			"total_chunks": count,
			"sources": per_source,
		}


_stores: Dict[str, VectorStore] = {}


def get_store(collection_name: str = "default") -> VectorStore:
	"""Simple singleton cache so callers reuse the same Chroma client/collection."""
	if collection_name not in _stores:
		_stores[collection_name] = VectorStore(collection_name=collection_name)
	return _stores[collection_name]
