FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PCN_DB_PATH=/data/civic.db PCN_EVIDENCE_DIR=/data/evidence
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --uid 10001 --create-home civic \
    && mkdir -p /data/evidence && chown -R civic:civic /data
COPY --chown=civic:civic backend/ /app/backend/
COPY --from=frontend --chown=civic:civic /build/dist /app/frontend/dist
USER civic
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/api/ready', timeout=4)"
CMD ["python", "backend/start.py"]
