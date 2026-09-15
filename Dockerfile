FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=5000

WORKDIR /app

# Fonts for the watermark (DejaVu covers Latin and Arabic/Persian).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY cleaner/ ./cleaner/
COPY cli/ ./cli/
COPY api/ ./api/

# Install the package itself so the `img-clean` console script exists in the
# image (it used to be missing: only the dependencies were installed).
RUN pip install --no-cache-dir . \
    && useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# The container runs the API by default, so the healthcheck can actually pass.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health').status == 200 else 1)"

CMD ["python", "-m", "api.server"]

# CLI usage (the console script is installed):
#   docker run --rm -v "$(pwd):/work" -w /work metadata-cleaner img-clean photo.jpg -o clean.jpg
# API usage (default CMD):
#   docker run --rm -p 5000:5000 metadata-cleaner
