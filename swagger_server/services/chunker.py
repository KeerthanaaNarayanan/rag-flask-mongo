import os
import re
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF


SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def _tokenize(text: str) -> List[str]:
	return text.split()


def _count_tokens(text: str) -> int:
	return len(_tokenize(text))


def _split_into_sentences(text: str) -> List[str]:
	cleaned = " ".join(text.split())
	if not cleaned:
		return []
	return [part.strip() for part in SENTENCE_BOUNDARY_RE.split(cleaned) if part.strip()]


def _window_from_sentences(
	sentences: List[str], chunk_size: int, overlap: int
) -> List[str]:
	if chunk_size <= 0:
		raise ValueError("chunk_size must be > 0")
	if overlap < 0:
		raise ValueError("overlap must be >= 0")
	if overlap >= chunk_size:
		raise ValueError("overlap must be less than chunk_size")

	# Build sentence chunks first; if any single sentence is too large, split it by tokens.
	chunks: List[str] = []
	current_sentences: List[str] = []
	current_tokens = 0

	for sentence in sentences:
		sentence_tokens = _count_tokens(sentence)

		if sentence_tokens > chunk_size:
			if current_sentences:
				chunks.append(" ".join(current_sentences).strip())
				current_sentences = []
				current_tokens = 0

			words = _tokenize(sentence)
			start = 0
			step = chunk_size - overlap
			while start < len(words):
				end = min(start + chunk_size, len(words))
				chunk = " ".join(words[start:end]).strip()
				if chunk:
					chunks.append(chunk)
				if end == len(words):
					break
				start += step
			continue

		would_be = current_tokens + sentence_tokens
		if would_be <= chunk_size:
			current_sentences.append(sentence)
			current_tokens = would_be
			continue

		if current_sentences:
			chunks.append(" ".join(current_sentences).strip())

		if overlap > 0 and chunks:
			overlap_words = _tokenize(chunks[-1])[-overlap:]
			overlap_text = " ".join(overlap_words).strip()
			current_sentences = [overlap_text, sentence] if overlap_text else [sentence]
			current_tokens = _count_tokens(" ".join(current_sentences))
			if current_tokens > chunk_size:
				# Keep the new sentence and trim overlap if needed.
				current_sentences = [sentence]
				current_tokens = sentence_tokens
		else:
			current_sentences = [sentence]
			current_tokens = sentence_tokens

	if current_sentences:
		chunks.append(" ".join(current_sentences).strip())

	return [c for c in chunks if c]


def _extract_text_by_page_from_pdf(pdf_path: str) -> List[Tuple[int, str]]:
	if not os.path.isfile(pdf_path):
		raise FileNotFoundError(f"PDF not found: {pdf_path}")

	pages: List[Tuple[int, str]] = []
	with fitz.open(pdf_path) as doc:
		for idx, page in enumerate(doc, start=1):
			text = page.get_text("text")
			pages.append((idx, text or ""))
	return pages


def split_text_into_overlapping_windows(
	*,
	text: Optional[str] = None,
	pdf_path: Optional[str] = None,
	source: Optional[str] = None,
	chunk_size: int = 256,
	overlap: int = 64,
) -> List[Dict[str, object]]:
	"""Split text into sentence-aware overlapping windows.

	Accepts either raw text or a PDF file path. Returns chunk records:
	{"text": str, "page": int | None, "source": str}
	"""
	if not text and not pdf_path:
		raise ValueError("Provide either text or pdf_path")
	if text and pdf_path:
		raise ValueError("Provide only one of text or pdf_path")

	records: List[Dict[str, object]] = []

	if pdf_path:
		resolved_source = source or os.path.basename(pdf_path)
		for page_num, page_text in _extract_text_by_page_from_pdf(pdf_path):
			sentences = _split_into_sentences(page_text)
			chunks = _window_from_sentences(sentences, chunk_size, overlap)
			for chunk in chunks:
				records.append({"text": chunk, "page": page_num, "source": resolved_source})
		return records

	resolved_source = source or "raw_text"
	sentences = _split_into_sentences(text or "")
	chunks = _window_from_sentences(sentences, chunk_size, overlap)
	for chunk in chunks:
		records.append({"text": chunk, "page": None, "source": resolved_source})
	return records


def chunk(
	text: Optional[str] = None,
	pdf_path: Optional[str] = None,
	source: Optional[str] = None,
	chunk_size: int = 256,
	chunk_overlap: int = 64,
) -> List[Dict[str, object]]:
	"""Compatibility wrapper for callers expecting `chunk(...)`."""
	return split_text_into_overlapping_windows(
		text=text,
		pdf_path=pdf_path,
		source=source,
		chunk_size=chunk_size,
		overlap=chunk_overlap,
	)
