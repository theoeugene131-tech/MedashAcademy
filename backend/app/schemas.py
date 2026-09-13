from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    level: str = "beginner"
    audience: str = "self-paced learners"
    modules_count: int = Field(default=3, ge=1, le=6)
    lectures_per_module: int = Field(default=3, ge=1, le=5)
    questions_per_quiz: int = Field(default=4, ge=2, le=8)
    include_audio: bool = True
    include_video: bool = True
    include_quiz: bool = True


class QuizQuestion(BaseModel):
    q: str
    options: list[str]
    answer_index: int
    explanation: str = ""


class Quiz(BaseModel):
    questions: list[QuizQuestion] = []


class Lecture(BaseModel):
    id: str
    title: str
    body_markdown: str
    key_points: list[str] = []
    duration_min: int = 5
    audio_url: str | None = None
    video_url: str | None = None
    slides: list[str] = []
    quiz: Quiz = Quiz()


class Module(BaseModel):
    id: str
    title: str
    objective: str = ""
    lectures: list[Lecture] = []


class Course(BaseModel):
    id: str
    topic: str
    level: str
    audience: str = ""
    description: str = ""
    created_at: str = ""
    modules: list[Module] = []


class GradeRequest(BaseModel):
    answers: list[int]  # one index per question


class GradeResponse(BaseModel):
    score: int
    total: int
    percent: float
    details: list[dict]
