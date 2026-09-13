# Medash Academy — AI MOOC Generator

Generate a complete mini-MOOC from one topic: multi-module **lectures** (Gemini),
**audio narration** (gTTS, local), **slide videos** (Pillow + moviepy/ffmpeg, local),
and auto-graded **quizzes**.

## Run backend

```
cd backend
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY (optional — works in mock mode without it)
uvicorn app.main:app --port 8001 --reload
```

API: http://localhost:8001/docs — media served at `/media/...`

## Run frontend

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5174

## Deploy live (Medash Academy)

- **Frontend → Vercel:** import this repo (Vite preset auto-detected, `frontend/vercel.json` included).
  Set env `VITE_API_URL=https://<your-backend-host>` then deploy. Works in demo mode without a backend.
- **Backend → Render/Railway (Docker):** build `backend/Dockerfile`
  (`backend/render.yaml` included). Set `GEMINI_API_KEY`. Health check: `/api/health`.
  Note: course JSON + media are local files — use a persistent disk on the host
  if you want courses to survive restarts.

## How it works

1. `POST /api/generate` → Gemini (`gemini-2.5-flash`) returns strict-JSON curriculum.
   No key / API error → deterministic mock template so media still works.
2. Per lecture: Pillow slides → gTTS mp3 (silent-WAV fallback offline) → moviepy mp4 (skipped if ffmpeg missing).
3. Courses saved to `backend/data/courses.json`. Quiz grading via
   `POST /api/courses/{id}/lectures/{lid}/grade`.
