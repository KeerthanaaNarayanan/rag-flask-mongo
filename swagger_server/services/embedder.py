import os
from threading import Lock
from typing import List, Optional

from flask import current_app
from sentence_transformers import SentenceTransformer


_model: Optional[SentenceTransformer] = None
_model_name: Optional[str] = None
_load_lock = Lock()


def _resolve_model_name(explicit_model_name: Optional[str] = None) -> str:
  if explicit_model_name:
    return explicit_model_name

  try:
    configured = current_app.config.get("EMBED_MODEL")
    if configured:
      return configured
  except RuntimeError:
    # No Flask app context; use env/default.
    pass

  return os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def load(model_name: Optional[str] = None) -> None:
  """Load the embedding model once and reuse it across requests."""
  global _model, _model_name

  resolved_model_name = _resolve_model_name(model_name)
  if _model is not None and _model_name == resolved_model_name:
    return

  with _load_lock:
    if _model is not None and _model_name == resolved_model_name:
      return
    _model = SentenceTransformer(resolved_model_name)
    _model_name = resolved_model_name


def embed(texts: List[str]) -> List[List[float]]:
  """Embed texts into the same vector space used for ingestion and query."""
  if not isinstance(texts, list):
    raise TypeError("texts must be a list[str]")
  if any(not isinstance(text, str) for text in texts):
    raise TypeError("texts must be a list[str]")
  if not texts:
    return []

  if _model is None:
    load()

  vectors = _model.encode(texts, normalize_embeddings=True)
  return vectors.tolist()