import connexion
import six
import os
import tempfile
from datetime import datetime, timezone

from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.ingest_body1 import IngestBody1  # noqa: E501
from swagger_server.models.ingest_response import IngestResponse  # noqa: E501
from swagger_server import util
from swagger_server.services import chunker, embedder, vector_store


def ingest_document(body):  # noqa: E501
    """Ingest a document

    Accepts either a **PDF file upload** (&#x60;multipart/form-data&#x60;) or **raw text** (&#x60;application/json&#x60;). The service will: 1. Extract text (PDF) or use the provided text directly 2. Split into overlapping chunks (&#x60;CHUNK_SIZE&#x60; tokens, &#x60;CHUNK_OVERLAP&#x60; overlap) 3. Embed all chunks in a single batch using &#x60;sentence-transformers&#x60; 4. Store each chunk as a MongoDB document with its embedding vector  Re-ingesting the same &#x60;source&#x60; name will add duplicate chunks. Use &#x60;DELETE /collections/{source}&#x60; to clear a source before re-ingesting.  # noqa: E501

    :param body: 
    :type body: dict | bytes

    :rtype: IngestResponse
    """
    try:
        chunk_size = int(os.getenv("CHUNK_SIZE", "256"))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "64"))

        if connexion.request.is_json:
            body = IngestBody1.from_dict(connexion.request.get_json())  # noqa: E501
            text = (body.text or "").strip()
            source = (body.source or "").strip()
            if not text:
                return ErrorResponse(error="validation_error", message="Field 'text' is required and cannot be empty."), 400
            if not source:
                return ErrorResponse(error="validation_error", message="Field 'source' is required and cannot be empty."), 400

            collection = (body.collection_name or "default").strip() or "default"
            chunks = chunker.chunk(
                text=text,
                source=source,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        else:
            uploaded = connexion.request.files.get("file") if hasattr(connexion.request, "files") else None
            if uploaded is None or not getattr(uploaded, "filename", ""):
                return ErrorResponse(error="validation_error", message="Provide either JSON body or multipart file upload."), 400

            source = os.path.basename(uploaded.filename)
            collection = (connexion.request.form.get("collection_name", "default") or "default").strip() or "default"

            suffix = os.path.splitext(source)[1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                uploaded.save(tmp.name)
                temp_path = tmp.name

            try:
                chunks = chunker.chunk(
                    pdf_path=temp_path,
                    source=source,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        if not chunks:
            return ErrorResponse(error="parse_error", message="No chunks were produced from input."), 422

        for idx, item in enumerate(chunks):
            item["chunk_index"] = idx

        embeddings = embedder.embed([str(item.get("text", "")) for item in chunks])
        inserted = vector_store.get_store(collection).add_documents(chunks, embeddings)

        return IngestResponse(
            chunk_count=inserted,
            source=source,
            collection_name=collection,
            ingested_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        return ErrorResponse(error="parse_error", message=f"Ingestion failed: {exc}"), 422
