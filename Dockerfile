# Pinned base for reproducible builds. Refresh digest with:
#   docker buildx imagetools inspect python:3.11.9-slim-bookworm
FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Font for watermark (pinned for bookworm; bump with base image).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu=2.37-2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cleaner/ ./cleaner/
COPY cli/ ./cli/
COPY api/ ./api/
COPY pyproject.toml README.md ./

# Run as non-root
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" || exit 1

# Default: show CLI help. Override for API:
#   docker run --rm -p 5000:5000 metadata-cleaner python -m api.server
# Hardened API example:
#   docker run --rm --read-only --tmpfs /tmp -p 5000:5000 \
#     --memory=512m --cpus=1 --pids-limit=64 \
#     -e MAX_UPLOAD_MB=16 -e RATE_LIMIT_PER_MIN=30 \
#     metadata-cleaner python -m api.server
CMD ["python", "-m", "cli.main", "--help"]
