FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 REPOLENS_ENV=production \
    REPOLENS_AUTH_DIR=/data/auth REPOLENS_REPORT_DIR=/data/reports REPOLENS_CHROMA_PATH=/data/chroma REPOLENS_EMBED_CACHE_DIR=/data/embedding-cache
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN useradd --uid 10001 --create-home appuser && mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser
VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "-c", "python -m backend.database.schema_migrations upgrade && python -m backend.database.schema_migrations verify && exec uvicorn backend.api.api:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
