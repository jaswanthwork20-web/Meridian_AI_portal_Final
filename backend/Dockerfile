FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    HF_HOME=/home/app/.cache/huggingface \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY --chown=10001:10001 . ./
RUN mkdir -p /app/backend/data /app/backend/database /app/backend/uploaded_tax_documents \
    && mkdir -p /home/app/.cache/huggingface \
    && chown -R 10001:10001 /app/backend /home/app

USER 10001:10001
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
