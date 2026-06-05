FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	VIRTUAL_ENV=/opt/venv \
	PATH="/opt/venv/bin:$PATH" \
	HF_HOME=/opt/hf-home \
	SENTENCE_TRANSFORMERS_HOME=/opt/sentence-transformers \
	EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2

WORKDIR /build

RUN python -m venv "$VIRTUAL_ENV"

COPY requirements.txt /build/

RUN pip install --upgrade pip && \
	pip install -r requirements.txt

# Pre-download embedding model at build time to avoid first-request startup delay.
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ.get('EMBED_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'))"


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	VIRTUAL_ENV=/opt/venv \
	PATH="/opt/venv/bin:$PATH" \
	HF_HOME=/opt/hf-home \
	SENTENCE_TRANSFORMERS_HOME=/opt/sentence-transformers

WORKDIR /usr/src/app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf-home /opt/hf-home
COPY --from=builder /opt/sentence-transformers /opt/sentence-transformers

# Copy app only in runtime image.
COPY swagger_server /usr/src/app/swagger_server

EXPOSE 8080

ENTRYPOINT ["python", "-m", "swagger_server"]