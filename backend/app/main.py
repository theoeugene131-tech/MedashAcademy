from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import store
from .ai_generator import generate_course
from .config import settings
from .media import MEDIA_ROOT, make_audio, make_slides, make_video
from .schemas import Course, GenerateRequest, GradeRequest, GradeResponse

app = FastAPI(title="Medash Academy — AI MOOC Generator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


@app.get("/api/health")
def health():
    return {"ok": True, "gemini_configured": bool(settings.gemini_api_key)}


@app.post("/api/generate", response_model=Course)
def generate(req: GenerateRequest):
    course = generate_course(req)

    # Media pipeline per lecture (local, zero-cost).
    for module in course.modules:
        for lec in module.lectures:
            slides = make_slides(course.id, lec.id, lec.title, lec.key_points)
            lec.slides = slides
            audio_url = None
            if req.include_audio:
                audio_url = make_audio(course.id, lec.id, lec.title, lec.body_markdown, lec.key_points)
                lec.audio_url = audio_url
            if req.include_video:
                slide_names = [u.rsplit("/", 1)[-1] for u in slides]
                audio_name = audio_url.rsplit("/", 1)[-1] if audio_url else None
                lec.video_url = make_video(course.id, lec.id, slide_names, audio_name)

    store.save_course(course)
    return course


@app.get("/api/courses", response_model=list[Course])
def get_courses():
    return store.list_courses()


@app.get("/api/courses/{course_id}", response_model=Course)
def get_course(course_id: str):
    course = store.get_course(course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return course


@app.post("/api/courses/{course_id}/lectures/{lecture_id}/grade", response_model=GradeResponse)
def grade(course_id: str, lecture_id: str, body: GradeRequest):
    course = store.get_course(course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    for m in course.modules:
        for lec in m.lectures:
            if lec.id == lecture_id:
                questions = lec.quiz.questions
                details = []
                score = 0
                for i, q in enumerate(questions):
                    picked = body.answers[i] if i < len(body.answers) else -1
                    correct = picked == q.answer_index
                    score += 1 if correct else 0
                    details.append(
                        {
                            "question": q.q,
                            "picked": picked,
                            "correct": q.answer_index,
                            "is_correct": correct,
                            "explanation": q.explanation,
                            "options": q.options,
                        }
                    )
                total = len(questions)
                return GradeResponse(
                    score=score,
                    total=total,
                    percent=round(100 * score / total, 1) if total else 0,
                    details=details,
                )
    raise HTTPException(404, "Lecture not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
