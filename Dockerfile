# Medash Academy — backend API service for the MOOC generator
# (repo root; frontend deploys to Vercel separately).

FROM python:3.12-slim

WORKDIR /srv/app

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# No system apt at all: media uses bundled binaries —
#   ffmpeg  -> imageio-ffmpeg static binary (Python package)
#   fonts   -> Pillow's built-in DejaVuSans
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
RUN mkdir -p /srv/app/data

EXPOSE 8001
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
