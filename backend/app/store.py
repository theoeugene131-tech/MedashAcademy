"""Tiny JSON-file store (no Postgres needed for the demo)."""
from __future__ import annotations

import json
from pathlib import Path

from .config import settings
from .schemas import Course, Enrollment

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / settings.data_file
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
ENROLL_FILE = BASE / "data" / "enrollments.json"
ENROLL_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_all() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_all(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_course(course: Course) -> None:
    data = _read_all()
    data[course.id] = course.model_dump()
    _write_all(data)


def get_course(course_id: str) -> Course | None:
    data = _read_all()
    raw = data.get(course_id)
    if not raw:
        return None
    try:
        return Course(**raw)
    except Exception:
        return None


def list_courses() -> list[Course]:
    data = _read_all()
    out: list[Course] = []
    for raw in data.values():
        try:
            out.append(Course(**raw))
        except Exception:
            continue
    # newest first
    out.sort(key=lambda c: c.created_at, reverse=True)
    return out


def _read_enrollments() -> dict:
    if not ENROLL_FILE.exists():
        return {}
    try:
        return json.loads(ENROLL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_enrollments(data: dict) -> None:
    ENROLL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_enrollment(enrollment: Enrollment) -> None:
    data = _read_enrollments()
    data[enrollment.id] = enrollment.model_dump()
    _write_enrollments(data)


def get_enrollment(enrollment_id: str) -> Enrollment | None:
    raw = _read_enrollments().get(enrollment_id)
    if not raw:
        return None
    try:
        return Enrollment(**raw)
    except Exception:
        return None


def list_enrollments() -> list[Enrollment]:
    out: list[Enrollment] = []
    for raw in _read_enrollments().values():
        try:
            out.append(Enrollment(**raw))
        except Exception:
            continue
    out.sort(key=lambda e: e.enrolled_at, reverse=True)
    return out
