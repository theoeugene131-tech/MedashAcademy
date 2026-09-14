# Medash Academy — AI MOOC Generator

Generate a complete mini-MOOC from one topic: multi-module **lectures** (Gemini),
**audio narration** (gTTS, local), **slide videos** (Pillow + moviepy/ffmpeg, local),
and auto-graded **quizzes**.

## Run backend

```
cd mooc-generator/backend
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY (optional — works in mock mode without it)
uvicorn app.main:app --port 8001 --reload
```

API: http://localhost:8001/docs — media served at `/media/...`

## Run frontend

```
cd mooc-generator/frontend
npm install
npm run dev
```

Open http://localhost:5174

## Deploy live (Medash Academy)

- **Frontend → Vercel:** import `mooc-generator/frontend` as a Vite project.
  Set env `VITE_API_URL=https://<your-backend-host>` then deploy.
- **Backend → Render/Railway (Docker):** build `mooc-generator/backend/Dockerfile`
  (`render.yaml` included). Set `GEMINI_API_KEY`. Health check: `/api/health`.
  Note: course JSON + media are local files — use a persistent disk on the host
  if you want courses to survive restarts.

## How it works

1. `POST /api/generate` → Gemini (`gemini-3.6-flash`) returns strict-JSON curriculum
   written against an instructional-design spec: per-lecture objectives, prerequisites,
   deep 400-700 word bodies (core concept + example, walkthrough, misconceptions,
   hands-on practice), key points, takeaways, further reading, and understanding-testing
   MCQs. Output passes a quality gate with one automatic retry.
   No key / API error → tagged `generated_by: "template"` offline stub so students
   always know which content is real AI vs. placeholder.
2. Per lecture: Pillow slides → gTTS mp3 (silent-WAV fallback offline) → ffmpeg slide video (direct, fast).
3. Courses saved to `backend/data/courses.json`. Quiz grading via
   `POST /api/courses/{id}/lectures/{lid}/grade`.
4. **Enrollment & certificates**: `POST /api/enroll` with a student name gates
   certification. Each quiz is graded via
   `POST /api/enrollments/{eid}/lectures/{lid}/grade`; passing every quiz
   (≥70% each) **automatically issues a certificate** (`GET /api/certificates/{id}`
   or the built-in print/PDF view). `data/enrollments.json` keeps all records.
