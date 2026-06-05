import connexion
import six
import os
import time
from datetime import datetime, timezone

from swagger_server.models.collections_response import CollectionsResponse  # noqa: E501
from swagger_server.models.collections_response_sources import CollectionsResponseSources  # noqa: E501
from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.health_response import HealthResponse  # noqa: E501
from swagger_server.models.health_response_dependencies import HealthResponseDependencies  # noqa: E501
from swagger_server.models.health_response_dependencies_embedding_model import HealthResponseDependenciesEmbeddingModel  # noqa: E501
from swagger_server.models.health_response_dependencies_llm import HealthResponseDependenciesLlm  # noqa: E501
from swagger_server.models.health_response_dependencies_mongodb import HealthResponseDependenciesMongodb  # noqa: E501
from swagger_server.models.inline_response200 import InlineResponse200  # noqa: E501
from swagger_server import util
from swagger_server.services import embedder, vector_store


_START_TIME = time.time()


def delete_source(source):  # noqa: E501
    """Delete all chunks for a source

    Removes all MongoDB documents matching the given &#x60;source&#x60; identifier. Use this before re-ingesting an updated version of a document to avoid duplicate chunks polluting retrieval results.  # noqa: E501

    :param source: The source identifier to delete (e.g. filename or slug)
    :type source: str

    :rtype: InlineResponse200
    """
    return 'do some magic!'


def health_check():  # noqa: E501
    """Service health check

    Returns the operational status of all service dependencies: - **embedding_model**: whether &#x60;sentence-transformers&#x60; is loaded and ready - **mongodb**: whether the PyMongo connection is live (runs a &#x60;ping&#x60; command) - **llm**: whether the configured LLM (OpenAI or Ollama) is reachable  # noqa: E501


    :rtype: HealthResponse
    """
    embed_status = "ok"
    embed_error = None
    embed_dimensions = None
    embed_model_name = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    if getattr(embedder, "_model", None) is None:
        embed_status = "error"
        embed_error = "embedding model is not loaded"
    else:
        try:
            sample_vec = embedder.embed(["health check"])[0]
            embed_dimensions = len(sample_vec)
        except Exception as exc:
            embed_status = "error"
            embed_error = str(exc)

    chroma_status = "ok"
    chroma_error = None
    chroma_ping_ms = None
    try:
        started = time.time()
        vector_store.get_store("default").get_collection_info()
        chroma_ping_ms = int((time.time() - started) * 1000)
    except Exception as exc:
        chroma_status = "error"
        chroma_error = str(exc)

    llm_provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if llm_provider not in {"openai", "ollama"}:
        llm_provider = "openai"

    llm_model = (
        os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if llm_provider == "openai"
        else os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    )
    llm_status = "ok"
    llm_error = None
    if llm_provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
        llm_status = "error"
        llm_error = "OPENAI_API_KEY not set; configure key or set LLM_PROVIDER=ollama"

    overall_status = "healthy"
    if embed_status == "error" or chroma_status == "error":
        overall_status = "unhealthy"
    elif llm_status == "error":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=os.getenv("APP_VERSION", "0.1.0"),
        uptime_seconds=int(time.time() - _START_TIME),
        dependencies=HealthResponseDependencies(
            embedding_model=HealthResponseDependenciesEmbeddingModel(
                status=embed_status,
                model=embed_model_name,
                dimensions=embed_dimensions,
                error=embed_error,
            ),
            mongodb=HealthResponseDependenciesMongodb(
                status=chroma_status,
                ping_ms=chroma_ping_ms,
                error=chroma_error,
            ),
            llm=HealthResponseDependenciesLlm(
                status=llm_status,
                provider=llm_provider,
                model=llm_model,
                error=llm_error,
            ),
        ),
    )


def list_collections():  # noqa: E501
    """List all ingested sources

    Returns all distinct document sources currently stored in MongoDB, along with chunk counts and ingestion timestamps. Useful for confirming what has been indexed before querying.  # noqa: E501


    :rtype: CollectionsResponse
    """
    try:
        store = vector_store.get_store("default")
        info = store.get_collection_info()

        # Build per-source ingestion timestamps from stored metadata.
        source_latest = {}
        total = int(info.get("total_chunks", 0))
        if total > 0:
            peek = store._collection.peek(limit=total)
            metadatas = peek.get("metadatas", []) if peek else []
            for md in metadatas:
                if not md:
                    continue
                source = str(md.get("source", "unknown"))
                ts = md.get("ingested_at")
                if ts and (source not in source_latest or str(ts) > str(source_latest[source])):
                    source_latest[source] = ts

        sources = []
        for source_name, count in sorted((info.get("sources") or {}).items()):
            ts = source_latest.get(source_name)
            if ts:
                try:
                    ingested_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except ValueError:
                    ingested_at = datetime.now(timezone.utc)
            else:
                ingested_at = datetime.now(timezone.utc)

            sources.append(
                CollectionsResponseSources(
                    source=source_name,
                    chunk_count=int(count),
                    ingested_at=ingested_at,
                )
            )

        return CollectionsResponse(total_chunks=int(info.get("total_chunks", 0)), sources=sources)
    except Exception as exc:
        return ErrorResponse(error="internal_error", message=f"Failed to list collections: {exc}"), 500
