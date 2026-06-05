import fitz
import pytest

from swagger_server.services import chunker


def _tokens(text):
    return text.split()


def test_chunk_sentence_boundaries_and_overlap():
    text = (
        "One two three four. "
        "Five six seven eight. "
        "Nine ten eleven twelve."
    )

    chunks = chunker.split_text_into_overlapping_windows(
        text=text,
        source="doc.txt",
        chunk_size=6,
        overlap=2,
    )

    assert len(chunks) == 3
    assert all(item["source"] == "doc.txt" for item in chunks)
    assert all(item["page"] is None for item in chunks)

    chunk_texts = [item["text"] for item in chunks]
    for first, second in zip(chunk_texts, chunk_texts[1:]):
        assert _tokens(first)[-2:] == _tokens(second)[:2]


def test_chunk_empty_whitespace_text_returns_no_chunks():
    chunks = chunker.split_text_into_overlapping_windows(text="   ", source="empty.txt")
    assert chunks == []


def test_chunk_without_text_or_pdf_raises_value_error():
    with pytest.raises(ValueError):
        chunker.split_text_into_overlapping_windows()


def test_pdf_extraction_by_page(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "First page sentence one. First page sentence two.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Second page sentence one. Second page sentence two.")
    doc.save(str(pdf_path))
    doc.close()

    chunks = chunker.split_text_into_overlapping_windows(
        pdf_path=str(pdf_path),
        source="sample.pdf",
        chunk_size=16,
        overlap=4,
    )

    assert len(chunks) >= 2
    pages = {item["page"] for item in chunks}
    assert pages == {1, 2}
    assert all(item["source"] == "sample.pdf" for item in chunks)