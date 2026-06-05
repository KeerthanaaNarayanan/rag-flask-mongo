import connexion
import six

from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.ingest_body1 import IngestBody1  # noqa: E501
from swagger_server.models.ingest_response import IngestResponse  # noqa: E501
from swagger_server import util


def ingest_document(file, collection_name):  # noqa: E501
    """Ingest a document

    Accepts either a **PDF file upload** (&#x60;multipart/form-data&#x60;) or **raw text** (&#x60;application/json&#x60;). The service will: 1. Extract text (PDF) or use the provided text directly 2. Split into overlapping chunks (&#x60;CHUNK_SIZE&#x60; tokens, &#x60;CHUNK_OVERLAP&#x60; overlap) 3. Embed all chunks in a single batch using &#x60;sentence-transformers&#x60; 4. Store each chunk as a MongoDB document with its embedding vector  Re-ingesting the same &#x60;source&#x60; name will add duplicate chunks. Use &#x60;DELETE /collections/{source}&#x60; to clear a source before re-ingesting.  # noqa: E501

    :param file: 
    :type file: strstr
    :param collection_name: 
    :type collection_name: str

    :rtype: IngestResponse
    """
    return 'do some magic!'


def ingest_document(body):  # noqa: E501
    """Ingest a document

    Accepts either a **PDF file upload** (&#x60;multipart/form-data&#x60;) or **raw text** (&#x60;application/json&#x60;). The service will: 1. Extract text (PDF) or use the provided text directly 2. Split into overlapping chunks (&#x60;CHUNK_SIZE&#x60; tokens, &#x60;CHUNK_OVERLAP&#x60; overlap) 3. Embed all chunks in a single batch using &#x60;sentence-transformers&#x60; 4. Store each chunk as a MongoDB document with its embedding vector  Re-ingesting the same &#x60;source&#x60; name will add duplicate chunks. Use &#x60;DELETE /collections/{source}&#x60; to clear a source before re-ingesting.  # noqa: E501

    :param body: 
    :type body: dict | bytes

    :rtype: IngestResponse
    """
    if connexion.request.is_json:
        body = IngestBody1.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
