import connexion
import six

from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.query_request import QueryRequest  # noqa: E501
from swagger_server.models.query_response import QueryResponse  # noqa: E501
from swagger_server import util


def query_documents(body):  # noqa: E501
    """Query ingested documents

    Ask a natural language question. The service will: 1. Embed the question using the same model used during ingestion 2. Fetch all embeddings from MongoDB and compute cosine similarity    (dot product on normalised vectors via numpy) 3. Retrieve the top-k most similar chunks 4. Build a prompt with the question + retrieved context 5. Call the configured LLM (OpenAI &#x60;gpt-4o-mini&#x60; or local Ollama) 6. Return the answer with source citations  Each source in the response includes a &#x60;score&#x60; (0–1) indicating how semantically similar that chunk was to the question.  # noqa: E501

    :param body: 
    :type body: dict | bytes

    :rtype: QueryResponse
    """
    if connexion.request.is_json:
        body = QueryRequest.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
