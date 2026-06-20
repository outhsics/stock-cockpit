# Stock Cockpit — single multi-stage image.
#
# Stage 1: build the React frontend -> /dist
# Stage 2: Python runtime that serves both the SPA (at /) and the API (at /api/*)
#
# Keeping everything in one image means one container, one port, one URL.

# ---------- Stage 1: frontend build ----------
FROM node:20-alpine AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_BASE=/api
RUN npm run build


# ---------- Stage 2: backend runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/app/ ./app/
COPY backend/scripts/ ./scripts/

# Built frontend copied from stage 1; FastAPI serves it at /
COPY --from=frontend-build /fe/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
