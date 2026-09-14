from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import store
from .ai_generator import generate_course
from .config import settings
from .media import MEDIA_ROOT, make_audio, make_slides, make_video
from .schemas import (
    Certificate,
    Course,
    EnrollRequest,
    Enrollment,
    GenerateRequest,
    GradeRequest,
    GradeResponse,
)

app = FastAPI(title="Medash Academy — AI MOOC Generator", version="0.1.0")

PASS_PERCENT = 70.0

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


def _find_lecture(course: Course, lecture_id: str):
    for m in course.modules:
        for lec in m.lectures:
            if lec.id == lecture_id:
                return lec
    return None


def _quiz_lecture_ids(course: Course) -> list[str]:
    ids = []
    for m in course.modules:
        for lec in m.lectures:
            if lec.quiz.questions:
                ids.append(lec.id)
    return ids


def _grade_label(avg: float) -> str:
    if avg >= 90:
        return "Distinction"
    if avg >= 80:
        return "Merit"
    return "Pass"


def _grade_questions(body: GradeRequest, questions) -> GradeResponse:
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


@app.post("/api/courses/{course_id}/lectures/{lecture_id}/grade", response_model=GradeResponse)
def grade(course_id: str, lecture_id: str, body: GradeRequest):
    course = store.get_course(course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    lec = _find_lecture(course, lecture_id)
    if not lec:
        raise HTTPException(404, "Lecture not found")
    return _grade_questions(body, lec.quiz.questions)


@app.post("/api/enroll", response_model=Enrollment)
def enroll(body: EnrollRequest):
    course = store.get_course(body.course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    if not course.modules or not _quiz_lecture_ids(course):
        raise HTTPException(400, "Course has no quizzes to complete")
    enrollment = Enrollment(
        id=uuid.uuid4().hex[:12],
        course_id=course.id,
        student_name=body.student_name.strip()[:120],
        enrolled_at=datetime.now(timezone.utc).isoformat(),
    )
    store.save_enrollment(enrollment)
    return enrollment


@app.get("/api/enrollments", response_model=list[Enrollment])
def enrollments():
    return store.list_enrollments()


@app.get("/api/enrollments/{enrollment_id}", response_model=Enrollment)
def get_enrollment(enrollment_id: str):
    enrollment = store.get_enrollment(enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")
    return enrollment


@app.post("/api/enrollments/{enrollment_id}/lectures/{lecture_id}/grade")
def grade_enrolled(enrollment_id: str, lecture_id: str, body: GradeRequest):
    enrollment = store.get_enrollment(enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")
    course = store.get_course(enrollment.course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    lec = _find_lecture(course, lecture_id)
    if not lec:
        raise HTTPException(404, "Lecture not found")

    quiz_ids = _quiz_lecture_ids(course)
    if lecture_id not in quiz_ids:
        raise HTTPException(400, "Lecture has no quiz to complete")

    result = _grade_questions(body, lec.quiz.questions)
    issued = False

    if result.percent >= PASS_PERCENT:
        enrollment.passed_lectures = list(sorted(set(enrollment.passed_lectures + [lecture_id])))
        # keep best score per lecture
        prev = enrollment.scores.get(lecture_id)
        if prev is None or result.percent > prev:
            enrollment.scores[lecture_id] = result.percent

        if enrollment.certificate is None and set(enrollment.passed_lectures) >= set(quiz_ids):
            avg = round(sum(enrollment.scores[l] for l in quiz_ids) / len(quiz_ids), 1)
            certificate = Certificate(
                id=uuid.uuid4().hex[:12],
                student_name=enrollment.student_name,
                course_id=course.id,
                course_topic=course.topic,
                issued_at=datetime.now(timezone.utc).isoformat(),
                completion_percent=avg,
                grade=_grade_label(avg),
            )
            enrollment.certificate = certificate
            issued = True

    store.save_enrollment(enrollment)
    return {
        "lecture_id": lecture_id,
        "result": result.model_dump(),
        "passed": result.percent >= PASS_PERCENT,
        "pass_percent": PASS_PERCENT,
        "progress": {"passed": len(enrollment.passed_lectures), "total": len(quiz_ids)},
        "issued": issued,
        "certificate": enrollment.certificate.model_dump() if enrollment.certificate else None,
    }


@app.get("/api/certificates/{certificate_id}", response_model=Certificate)
def get_certificate(certificate_id: str):
    for enrollment in store.list_enrollments():
        if enrollment.certificate and enrollment.certificate.id == certificate_id:
            return enrollment.certificate
    raise HTTPException(404, "Certificate not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
