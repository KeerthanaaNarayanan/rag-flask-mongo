import connexion
import six
import json
import time

from flask import Response, stream_with_context

from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.query_request import QueryRequest  # noqa: E501
from swagger_server.models.query_response import QueryResponse  # noqa: E501
from swagger_server.models.source_chunk import SourceChunk  # noqa: E501
from swagger_server import util
from swagger_server.services import embedder, llm, vector_store


def _to_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _chunk_to_model(item):
    return SourceChunk(
        text=str(item.get("text", "")),
        source=str(item.get("source", "unknown")),
        page=item.get("page"),
        chunk_index=item.get("chunk_index"),
        score=item.get("score"),
    )


def query_documents(body):  # noqa: E501
    """Query ingested documents

    Ask a natural language question. The service will: 1. Embed the question using the same model used during ingestion 2. Fetch all embeddings from MongoDB and compute cosine similarity    (dot product on normalised vectors via numpy) 3. Retrieve the top-k most similar chunks 4. Build a prompt with the question + retrieved context 5. Call the configured LLM (OpenAI &#x60;gpt-4o-mini&#x60; or local Ollama) 6. Return the answer with source citations  Each source in the response includes a &#x60;score&#x60; (0–1) indicating how semantically similar that chunk was to the question.  # noqa: E501

    :param body: 
    :type body: dict | bytes

    :rtype: QueryResponse
    """
    started = time.time()
    try:
        if not connexion.request.is_json:
            return ErrorResponse(error="validation_error", message="Expected application/json body."), 400

        body = QueryRequest.from_dict(connexion.request.get_json())  # noqa: E501
        question = (body.question or "").strip()
        if not question:
            return ErrorResponse(error="validation_error", message="Field 'question' is required and cannot be empty."), 400

        top_k = int(body.top_k or 4)
        if top_k <= 0:
            return ErrorResponse(error="validation_error", message="Field 'top_k' must be > 0."), 400

        source_filter = (body.source_filter or "").strip()
        collection = (body.collection_name or "default").strip() or "default"

        q_embedding = embedder.embed([question])[0]
        retrieved = vector_store.get_store(collection).query(q_embedding, top_k)

        if source_filter:
            retrieved = [row for row in retrieved if str(row.get("source", "")) == source_filter]

        if not retrieved:
            return ErrorResponse(error="no_documents", message="No relevant chunks found. Please ingest documents first."), 404

        is_streaming = _to_bool(connexion.request.args.get("streaming", "false"))

        if is_streaming:
            stream_data = llm.stream_answer_with_context(question=question, retrieved_chunks=retrieved)

            @stream_with_context
            def event_stream():
                yield "event: sources\n"
                yield f"data: {json.dumps(stream_data['sources'])}\n\n"

                answer_parts = []
                for token in stream_data["tokens"]:
                    answer_parts.append(token)
                    yield "event: token\n"
                    yield f"data: {json.dumps({'text': token})}\n\n"

                latency_ms = int((time.time() - started) * 1000)
                yield "event: done\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "answer": "".join(answer_parts),
                            "model_used": stream_data["model_used"],
                            "provider_used": stream_data["provider_used"],
                            "latency_ms": latency_ms,
                        }
                    )
                    + "\n\n"
                )

            return Response(
                event_stream(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        llm_result = llm.generate_answer(question=question, retrieved_chunks=retrieved)
        sources = [_chunk_to_model(item) for item in llm_result["sources"]]
        latency_ms = int((time.time() - started) * 1000)

        return QueryResponse(
            answer=llm_result["answer"],
            sources=sources,
            model_used=llm_result["model_used"],
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return ErrorResponse(error="internal_error", message=f"Query failed: {exc}"), 500
