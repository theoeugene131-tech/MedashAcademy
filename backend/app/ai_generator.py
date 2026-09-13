"""Course content generation via Gemini, with offline mock fallback.

If GEMINI_API_KEY is missing or the API call fails, we generate a
deterministic, genuinely usable course template so the app (and its
audio/video pipeline) works out of the box.
"""
from __future__ import annotations

import json
import re
import uuid

from .config import settings
from .schemas import Course, GenerateRequest, Lecture, Module, Quiz, QuizQuestion


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


PROMPT_TEMPLATE = """You are an expert MOOC instructional designer.
Design a complete mini-course as STRICT JSON (no markdown fences, no commentary).

Topic: {topic}
Level: {level}
Audience: {audience}
Modules: {modules_count}, Lectures per module: {lectures_per_module}, Quiz questions per lecture: {questions_per_quiz}

Return JSON with exactly this shape:
{{
  "description": "2-3 sentence course overview",
  "modules": [
    {{
      "title": "Module title",
      "objective": "One sentence learning objective",
      "lectures": [
        {{
          "title": "Lecture title",
          "body_markdown": "Full lecture text, 300-500 words, with ## headings and a worked example",
          "key_points": ["point 1", "point 2", "point 3", "point 4"],
          "duration_min": 5,
          "quiz": [
            {{"q": "question?", "options": ["a","b","c","d"], "answer_index": 0, "explanation": "why"}}
          ]
        }}
      ]
    }}
  ]
}}
Rules: 4 options per question, answer_index 0-3, body_markdown must be substantive (not lorem ipsum).
"""


def _call_gemini(req: GenerateRequest) -> dict | None:
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = PROMPT_TEMPLATE.format(
            topic=req.topic,
            level=req.level,
            audience=req.audience,
            modules_count=req.modules_count,
            lectures_per_module=req.lectures_per_module,
            questions_per_quiz=req.questions_per_quiz,
        )
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=12000, temperature=0.7),
        )
        text = (resp.text or "").strip()
        # Strip ```json fences if the model adds them despite instructions.
        text = re.sub(r"^```(?:json)?\s*", "", text).strip()
        text = re.sub(r"\s*```$", "", text).strip()
        return json.loads(text)
    except Exception as e:  # network, quota, bad JSON -> fall back to mock
        print(f"[ai_generator] Gemini failed, using mock template: {e}")
        return None


def _mock_course(req: GenerateRequest) -> dict:
    """Deterministic template course — real structure, topic-aware wording."""
    t = req.topic.strip()
    modules = []
    for m in range(1, req.modules_count + 1):
        lectures = []
        for lec in range(1, req.lectures_per_module + 1):
            quiz = []
            for q in range(1, req.questions_per_quiz + 1):
                quiz.append(
                    {
                        "q": f"In the context of {t} (module {m}, lecture {lec}), which statement is most accurate? (Q{q})",
                        "options": [
                            f"Core principle of {t} applied correctly",
                            "A common misconception about " + t,
                            "An unrelated fact",
                            "The opposite of best practice",
                        ],
                        "answer_index": 0,
                        "explanation": f"The first option reflects the key idea taught in lecture {lec} of module {m}.",
                    }
                )
            lectures.append(
                {
                    "title": f"{t}: Module {m} Lecture {lec}",
                    "body_markdown": (
                        f"## Lecture {m}.{lec} — {t}\n\n"
                        f"This lecture covers a key building block of **{t}** for {req.level} learners.\n\n"
                        f"### 1. The big idea\n{t} works best when you understand the fundamentals before "
                        f"jumping to tools. We introduce the core vocabulary, a mental model, and where "
                        f"this lecture fits in the module.\n\n"
                        f"### 2. Worked example\nImagine applying {t} to a small real project: define the goal, "
                        f"break it into 3 steps, try the simplest version first, then measure and iterate. "
                        f"That loop — goal, attempt, feedback, refine — is the pattern behind every module in this course.\n\n"
                        f"### 3. Common mistakes\n- Skipping foundations and copying solutions blindly\n"
                        f"- Optimising too early instead of getting a baseline working\n"
                        f"- Not writing down what you tried and what happened\n\n"
                        f"### 4. Try it yourself\n1. Summarise this lecture in 3 sentences.\n"
                        f"2. Apply one idea from it to your own {t} project.\n3. Take the quiz below to check understanding.\n"
                    ),
                    "key_points": [
                        f"Core vocabulary of {t} (module {m})",
                        "Mental model: goal → attempt → feedback → refine",
                        "Worked example you can replicate in 15 minutes",
                        "Top 3 beginner mistakes and how to avoid them",
                    ],
                    "duration_min": 5,
                    "quiz": quiz,
                }
            )
        modules.append(
            {
                "title": f"Module {m}: {t} foundations ({m}/{req.modules_count})",
                "objective": f"By the end of module {m}, you can explain and apply core {t} concepts.",
                "lectures": lectures,
            }
        )
    return {
        "description": f"A {req.level}-level, {req.modules_count}-module hands-on course on {t} for {req.audience}. Includes full lectures, narration audio, slide videos, and auto-graded quizzes.",
        "modules": modules,
    }


def generate_course(req: GenerateRequest) -> Course:
    from datetime import datetime, timezone

    raw = _call_gemini(req) or _mock_course(req)
    course_id = uuid.uuid4().hex[:12]
    modules: list[Module] = []
    for mi, m in enumerate(raw.get("modules", [])[: req.modules_count], start=1):
        lectures: list[Lecture] = []
        for li, lec in enumerate(m.get("lectures", [])[: req.lectures_per_module], start=1):
            questions = []
            if req.include_quiz:
                for q in (lec.get("quiz") or [])[: req.questions_per_quiz]:
                    opts = list(q.get("options", []))[:4]
                    while len(opts) < 4:
                        opts.append(f"Option {len(opts) + 1}")
                    try:
                        ans = int(q.get("answer_index", 0))
                    except (TypeError, ValueError):
                        ans = 0
                    questions.append(
                        QuizQuestion(
                            q=str(q.get("q", "Review question"))[:500],
                            options=opts,
                            answer_index=max(0, min(3, ans)),
                            explanation=str(q.get("explanation", ""))[:500],
                        )
                    )
            lectures.append(
                Lecture(
                    id=f"{course_id}-m{mi}l{li}-{_short_id()}",
                    title=str(lec.get("title", f"Lecture {mi}.{li}"))[:200],
                    body_markdown=str(lec.get("body_markdown", ""))[:12000],
                    key_points=[str(k)[:200] for k in (lec.get("key_points") or [])[:6]],
                    duration_min=int(lec.get("duration_min", 5) or 5),
                    quiz=Quiz(questions=questions),
                )
            )
        modules.append(
            Module(
                id=f"{course_id}-m{mi}-{_short_id()}",
                title=str(m.get("title", f"Module {mi}"))[:200],
                objective=str(m.get("objective", ""))[:500],
                lectures=lectures,
            )
        )
    return Course(
        id=course_id,
        topic=req.topic,
        level=req.level,
        audience=req.audience,
        description=str(raw.get("description", ""))[:1000],
        created_at=datetime.now(timezone.utc).isoformat(),
        modules=modules,
    )
