"""Course content generation via Gemini, with offline template fallback.

Primary path: Gemini returns a deep, course-specific curriculum written
against a strict instructional-design spec. A quality gate validates the
output and retries once before accepting. The deterministic template is
only a very last resort (no key / API down) and is tagged as such.

Every course is tagged `generated_by: "gemini" | "template"` so students
can tell real AI content from the offline stub.
"""
from __future__ import annotations

import json
import re
import uuid

from .config import settings
from .schemas import Course, GenerateRequest, Lecture, Module, Quiz, QuizQuestion


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


PROMPT_TEMPLATE = """You are a senior instructional designer and a subject-matter expert in {topic}.
Design a genuinely valuable, complete mini-course as STRICT JSON (no markdown fences, no commentary).

Topic: {topic}
Level: {level}
Audience: {audience}
Structure: {modules_count} modules, {lectures_per_module} lectures per module, {questions_per_quiz} MCQ per lecture quiz.

## Quality rules
- Every lecture MUST be specifically about {topic}. No generic filler, no lorem ipsum,
  no "Module N" placeholders, no advice that would apply to any topic unchanged.
- Lectures inside a module build on each other: early lectures teach fundamentals,
  later ones apply and extend them (clear progression of difficulty across the whole course).
- body_markdown MUST be 400-700 words of markdown with exactly these sections:
  - "## <hook>" — why this matters to a {level} learner (one vivid, concrete reason)
  - "### Core concept" — clear explanation WITH a concrete example and an analogy from everyday life
  - "### Step-by-step walkthrough" — numbered, actionable steps the learner can follow right now
  - "### Common misconceptions" — 2-3 mistakes {level} learners make and how to avoid them
  - "### Hands-on practice" — one concrete task tied to {topic} the learner should do now
- objective: what the learner can DO after this lecture (measurable verb, specific to {topic}).
- prerequisites: what they need before starting this lecture (specific, not "none").
- key_points: 4 crisp takeaways. practice: 2 concrete tasks. takeaways: 3 summary bullets.
- further_reading: 2 real, relevant resources (use specific known references for {topic}, not fake URLs).
- Quiz: {questions_per_quiz} meaningful multiple-choice questions that TEST UNDERSTANDING of THIS
  lecture's content (scenario-based where possible, not trivial recall). 4 options each,
  answer_index 0-3, and a short explanation of why the answer is correct.

## Return exactly this JSON shape
{{
  "description": "2-3 sentence course overview",
  "prerequisites": ["course-level prerequisite 1", "course-level prerequisite 2"],
  "objectives": ["course learning outcome 1", "course learning outcome 2", "course learning outcome 3"],
  "modules": [
    {{
      "title": "Module title",
      "objective": "One sentence module objective",
      "lectures": [
        {{
          "title": "Lecture title",
          "objective": "Measurable lecture objective",
          "prerequisites": ["one", "two"],
          "body_markdown": "400-700 words with the exact section headings described above",
          "key_points": ["p1","p2","p3","p4"],
          "practice": ["task 1","task 2"],
          "takeaways": ["t1","t2","t3"],
          "further_reading": ["resource 1","resource 2"],
          "duration_min": 8,
          "quiz": [
            {{"q":"question?","options":["a","b","c","d"],"answer_index":0,"explanation":"why"}}
          ]
        }}
      ]
    }}
  ]
}}
"""


def _strip_json_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip()).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    return text


def _call_gemini(req: GenerateRequest) -> dict | None:
    """One Gemini call; returns parsed JSON or None on any failure."""
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
            config=types.GenerateContentConfig(max_output_tokens=16000, temperature=0.7),
        )
        return json.loads(_strip_json_fences(resp.text or ""))
    except Exception as e:
        print(f"[ai_generator] Gemini call failed: {e}")
        return None


def _quality_ok(raw: dict, req: GenerateRequest) -> bool:
    """Cheap quality gate: enough lectures, substantive bodies, quizzes present."""
    if not isinstance(raw, dict):
        return False
    modules = raw.get("modules")
    if not isinstance(modules, list) or not modules:
        return False
    expected = req.modules_count * req.lectures_per_module
    seen = 0
    for m in modules:
        for l in m.get("lectures", []):
            seen += 1
            body = str(l.get("body_markdown", ""))
            if len(body) < 300 or "Core concept" not in body:
                return False
            if req.include_quiz and not l.get("quiz"):
                return False
    return seen >= max(1, int(expected * 0.6))


def _mock_course(req: GenerateRequest) -> dict:
    """Deterministic template course — real structure, topic-aware wording.
    Only used offline; always tagged as template so it's never mistaken for AI content."""
    t = req.topic.strip()
    modules = []
    for m in range(1, req.modules_count + 1):
        lectures = []
        for lec in range(1, req.lectures_per_module + 1):
            quiz = []
            if req.include_quiz:
                for q in range(1, req.questions_per_quiz + 1):
                    quiz.append(
                        {
                            "q": f"In the context of {t} (module {m}, lecture {lec}), which statement is most accurate? (Q{q})",
                            "options": [
                                f"Core principle of {t} applied correctly",
                                f"A common misconception about {t}",
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
                    "objective": f"Explain and apply the core {t} idea introduced in lecture {lec}.",
                    "prerequisites": [f"Basics of {t} from the earlier part of module {m}"],
                    "body_markdown": (
                        f"## Why this matters\n{t} is a practical skill, and this lecture builds the first "
                        f"building block you need for {req.level}-level work.\n\n"
                        f"### Core concept\n{t} works best when you understand the fundamentals before jumping "
                        f"to tools. This lecture introduces the core vocabulary and a mental model, and shows "
                        f"where it fits in the module.\n\n"
                        f"### Step-by-step walkthrough\n1. Define the goal behind your {t} task.\n"
                        f"2. Break it into three small steps.\n3. Try the simplest version first.\n"
                        f"4. Measure the result and refine once.\n\n"
                        f"### Common misconceptions\n- Skipping foundations and copying solutions blindly\n"
                        f"- Optimising too early instead of getting a baseline working\n"
                        f"- Not writing down what you tried and what happened\n\n"
                        f"### Hands-on practice\nTake a tiny {t} task you already have and apply the four "
                        f"steps above to it. Record the result.\n"
                    ),
                    "key_points": [
                        f"Core vocabulary of {t} (module {m})",
                        "Mental model: goal → attempt → feedback → refine",
                        "Worked example you can replicate in 15 minutes",
                        "Top 3 beginner mistakes and how to avoid them",
                    ],
                    "practice": [
                        f"Summarise this {t} lecture in three sentences.",
                        f"Apply one idea from it to a small {t} project of your own.",
                    ],
                    "takeaways": [
                        f"You understand the key {t} building block of module {m}.",
                        "You have a repeatable four-step practice loop.",
                        "You can recognise the top beginner mistakes.",
                    ],
                    "further_reading": [
                        f"Official documentation and beginner guides for {t}",
                        f"Community tutorials and forums discussing {t}",
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
        "description": f"A {req.level}-level, {req.modules_count}-module hands-on course on {t} for {req.audience}. "
                       f"Generated offline from a template — connect Gemini for deep, course-specific content.",
        "prerequisites": [f"No prior {t} experience required — a general interest is enough."],
        "objectives": [
            f"Explain the core ideas behind {t}",
            f"Apply {t} basics to a small real project",
            f"Recognise and avoid the most common {t} mistakes",
        ],
        "modules": modules,
    }


def generate_course(req: GenerateRequest) -> Course:
    from datetime import datetime, timezone

    source = "template"
    raw = _call_gemini(req)
    if _quality_ok(raw, req) if raw else False:
        source = "gemini"
    else:
        if raw is not None:
            print("[ai_generator] Gemini output failed quality gate — retrying once.")
            raw = _call_gemini(req)
            if _quality_ok(raw, req) if raw else False:
                source = "gemini"
    if raw is None or source == "template":
        raw = _mock_course(req)

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
                    objective=str(lec.get("objective", ""))[:500],
                    prerequisites=[str(p)[:200] for p in (lec.get("prerequisites") or [])[:5]],
                    body_markdown=str(lec.get("body_markdown", ""))[:20000],
                    key_points=[str(k)[:200] for k in (lec.get("key_points") or [])[:6]],
                    practice=[str(p)[:300] for p in (lec.get("practice") or [])[:5]],
                    takeaways=[str(t)[:300] for t in (lec.get("takeaways") or [])[:5]],
                    further_reading=[str(f)[:300] for f in (lec.get("further_reading") or [])[:5]],
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
        description=str(raw.get("description", ""))[:1200],
        prerequisites=[str(p)[:300] for p in (raw.get("prerequisites") or [])[:5]],
        objectives=[str(o)[:300] for o in (raw.get("objectives") or [])[:6]],
        generated_by=source,
        created_at=datetime.now(timezone.utc).isoformat(),
        modules=modules,
    )