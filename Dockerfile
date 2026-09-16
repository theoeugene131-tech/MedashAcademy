# Medash Academy — backend API service for Railway.
# Builds only backend/app (repo root); the frontend deploys to Vercel separately.
FROM python:3.12-slim

WORKDIR /srv/app

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# System ffmpeg fallback (media.py also prefers bundled imageio-ffmpeg binary).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
RUN mkdir -p /srv/app/data

# Railway injects PORT; default 8000 locally.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
