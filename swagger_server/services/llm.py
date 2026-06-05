import os
import json
from typing import Any, Dict, List, Optional, Tuple

import httpx


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _format_sources(chunks: List[Dict[str, Any]]) -> str:
	if not chunks:
		return "No sources were retrieved."

	lines: List[str] = []
	for idx, chunk in enumerate(chunks, start=1):
		source = str(chunk.get("source", "unknown"))
		page = chunk.get("page")
		page_str = f"p.{page}" if page is not None else "p.n/a"
		text = str(chunk.get("text", "")).strip()
		lines.append(f"[{idx}] {source} ({page_str})\n{text}")
	return "\n\n".join(lines)


def build_messages(question: str, retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
	"""Build RAG prompt messages with contract + numbered context sources."""
	system_message = (
		"You are a retrieval-grounded assistant. Follow this contract:\n"
		"1) Use only the provided sources for factual claims.\n"
		"2) If the answer is not in sources, say you do not have enough context.\n"
		"3) Be concise and accurate; do not fabricate details.\n"
		"4) Cite supporting source numbers like [1], [2] in the answer."
	)

	sources_block = _format_sources(retrieved_chunks)
	user_message = (
		"Retrieved sources:\n"
		f"{sources_block}\n\n"
		"Question:\n"
		f"{question}"
	)

	return [
		{"role": "system", "content": system_message},
		{"role": "user", "content": user_message},
	]


def _call_openai(messages: List[Dict[str, str]], model: str) -> Tuple[str, str]:
	api_key = os.getenv("OPENAI_API_KEY", "").strip()
	if not api_key:
		raise RuntimeError("OPENAI_API_KEY is missing")

	base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
	payload = {"model": model, "messages": messages}
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}

	with httpx.Client(timeout=60.0) as client:
		response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
		response.raise_for_status()
		data = response.json()

	answer = str((((data.get("choices") or [{}])[0].get("message") or {}).get("content", ""))).strip()
	return answer, model


def _call_ollama(messages: List[Dict[str, str]], model: str) -> Tuple[str, str]:
	ollama_url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
	payload = {
		"model": model,
		"messages": messages,
		"stream": False,
	}

	with httpx.Client(timeout=60.0) as client:
		response = client.post(f"{ollama_url}/api/chat", json=payload)
		response.raise_for_status()
		data = response.json()

	answer = str((data.get("message") or {}).get("content", "")).strip()
	return answer, model


def _stream_openai(messages: List[Dict[str, str]], model: str):
	api_key = os.getenv("OPENAI_API_KEY", "").strip()
	if not api_key:
		raise RuntimeError("OPENAI_API_KEY is missing")

	base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
	payload = {"model": model, "messages": messages, "stream": True}
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}

	with httpx.Client(timeout=None) as client:
		with client.stream("POST", f"{base_url}/chat/completions", json=payload, headers=headers) as response:
			response.raise_for_status()
			for line in response.iter_lines():
				if not line:
					continue
				if not line.startswith("data: "):
					continue
				data = line[6:].strip()
				if data == "[DONE]":
					break
				parsed = json.loads(data)
				delta = (((parsed.get("choices") or [{}])[0].get("delta") or {}).get("content", ""))
				if delta:
					yield str(delta)


def _stream_ollama(messages: List[Dict[str, str]], model: str):
	ollama_url = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
	payload = {
		"model": model,
		"messages": messages,
		"stream": True,
	}

	with httpx.Client(timeout=None) as client:
		with client.stream("POST", f"{ollama_url}/api/chat", json=payload) as response:
			response.raise_for_status()
			for line in response.iter_lines():
				if not line:
					continue
				parsed = json.loads(line)
				delta = str((parsed.get("message") or {}).get("content", ""))
				if delta:
					yield delta


def answer_with_context(
	question: str,
	retrieved_chunks: List[Dict[str, Any]],
	provider: Optional[str] = None,
	openai_model: str = DEFAULT_OPENAI_MODEL,
	ollama_model: str = DEFAULT_OLLAMA_MODEL,
) -> Dict[str, Any]:
	"""Generate an answer from retrieved chunks using OpenAI with Ollama fallback."""
	if not question or not str(question).strip():
		raise ValueError("question must be a non-empty string")

	messages = build_messages(str(question).strip(), retrieved_chunks)

	resolved_provider = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()

	if resolved_provider not in {"openai", "ollama"}:
		raise ValueError("provider must be 'openai' or 'ollama'")

	# Local-only mode if no key is present.
	if resolved_provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
		resolved_provider = "ollama"

	used_provider = resolved_provider
	used_model = openai_model if resolved_provider == "openai" else ollama_model

	try:
		if resolved_provider == "openai":
			answer_text, used_model = _call_openai(messages, openai_model)
		else:
			answer_text, used_model = _call_ollama(messages, ollama_model)
	except Exception:
		# Automatic local fallback for resiliency.
		if resolved_provider == "openai":
			answer_text, used_model = _call_ollama(messages, ollama_model)
			used_provider = "ollama"
		else:
			raise

	return {
		"answer": answer_text,
		"sources": retrieved_chunks,
		"provider_used": used_provider,
		"model_used": used_model,
	}


def generate_answer(
	question: str,
	retrieved_chunks: List[Dict[str, Any]],
	provider: Optional[str] = None,
	openai_model: str = DEFAULT_OPENAI_MODEL,
	ollama_model: str = DEFAULT_OLLAMA_MODEL,
) -> Dict[str, Any]:
	"""Compatibility wrapper used by controllers/services."""
	return answer_with_context(
		question=question,
		retrieved_chunks=retrieved_chunks,
		provider=provider,
		openai_model=openai_model,
		ollama_model=ollama_model,
	)


def stream_answer_with_context(
	question: str,
	retrieved_chunks: List[Dict[str, Any]],
	provider: Optional[str] = None,
	openai_model: str = DEFAULT_OPENAI_MODEL,
	ollama_model: str = DEFAULT_OLLAMA_MODEL,
) -> Dict[str, Any]:
	"""Stream answer tokens from OpenAI or Ollama with the same RAG prompt context."""
	if not question or not str(question).strip():
		raise ValueError("question must be a non-empty string")

	messages = build_messages(str(question).strip(), retrieved_chunks)
	resolved_provider = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()

	if resolved_provider not in {"openai", "ollama"}:
		raise ValueError("provider must be 'openai' or 'ollama'")

	if resolved_provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
		resolved_provider = "ollama"

	used_model = openai_model if resolved_provider == "openai" else ollama_model

	def _token_iterator():
		if resolved_provider == "openai":
			try:
				yield from _stream_openai(messages, openai_model)
				return
			except Exception:
				# Fallback to local streaming path if OpenAI streaming fails.
				yield from _stream_ollama(messages, ollama_model)
				return
		yield from _stream_ollama(messages, ollama_model)

	used_provider = resolved_provider
	if resolved_provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
		used_provider = "ollama"
		used_model = ollama_model

	return {
		"tokens": _token_iterator(),
		"sources": retrieved_chunks,
		"provider_used": used_provider,
		"model_used": used_model,
	}
