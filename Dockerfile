FROM node:24-slim AS web
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_URL="" VITE_PUBLIC_DEMO="true"
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 STATIC_DIR=/app/web
WORKDIR /app/backend
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /build/dist /app/web
COPY scripts/serve.py /app/scripts/serve.py
RUN useradd --create-home pulse && mkdir -p /data && chown -R pulse:pulse /data /app
USER pulse
EXPOSE 8000
# Runtime state belongs in the configured database, not the application image.
CMD ["python", "/app/scripts/serve.py"]
