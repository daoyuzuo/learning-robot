"""FastAPI surfaces for lessons, exercises, and evidence."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.exercise.grading import grade
from testbridge.lesson.renderer import render_lesson

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


class EvidenceRequest(BaseModel):
    lesson_id: str
    exercise_id: str
    response: Any = None
    hints_used: int = 0
    duration_ms: int = 0
    session_id: str | None = None


def _script_json(value: Any) -> str:
    """Serialize JSON so it cannot terminate its ``<script>`` container."""
    serialized = json.dumps(value, ensure_ascii=False)
    return (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def create_app(pack_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    pack_path = pack_dir or ROOT / "content-packs" / "sample-sensors"
    database = db_path or ROOT / "data" / "testbridge.db"
    pack = load_pack(pack_path)
    store = EvidenceStore(database)

    app = FastAPI(title="TestBridge")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'"
        )
        return response

    templates = Jinja2Templates(directory=str(BASE / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    assets_dir = pack.root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    def ctx(request: Request, **kwargs):
        return {"request": request, "pack": pack, **kwargs}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        modules = sorted(pack.modules.values(), key=lambda item: (item.order, item.id))
        lessons_by_module = {
            module.id: [pack.lessons[item] for item in module.lessons if item in pack.lessons]
            for module in modules
        }
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=ctx(request, modules=modules, lessons_by_module=lessons_by_module),
        )

    @app.get("/lesson/{lesson_id}", response_class=HTMLResponse)
    def lesson_page(request: Request, lesson_id: str):
        if lesson_id not in pack.lessons:
            raise HTTPException(status_code=404, detail="lesson not found")
        view = render_lesson(pack, lesson_id)
        exercise_data = _script_json(
            {exercise.id: exercise.model_dump(mode="json") for exercise in view.exercises}
        )
        return templates.TemplateResponse(
            request=request,
            name="lesson.html",
            context=ctx(request, view=view, exercise_data=exercise_data),
        )

    @app.get("/progress", response_class=HTMLResponse)
    def progress_page(request: Request):
        events = store.list(limit=200)
        return templates.TemplateResponse(
            request=request,
            name="progress.html",
            context=ctx(request, events=events, total=store.count()),
        )

    @app.post("/api/evidence")
    def submit_evidence(payload: EvidenceRequest):
        if payload.lesson_id not in pack.lessons:
            raise HTTPException(status_code=404, detail="lesson not found")
        exercise = pack.exercises.get(payload.exercise_id)
        if exercise is None:
            raise HTTPException(status_code=404, detail="exercise not found")
        result = grade(exercise, payload.response)
        event = new_event(
            kind="exercise_attempt",
            lesson_id=payload.lesson_id,
            exercise_id=payload.exercise_id,
            concept_ids=exercise.concepts,
            outcome=result.outcome,
            score=result.score,
            max_score=result.max_score,
            payload={
                "response": payload.response,
                "hints_used": payload.hints_used,
                "duration_ms": payload.duration_ms,
                "feedback": result.feedback,
                "details": result.details,
            },
            source="web",
            session_id=payload.session_id,
        )
        store.append(event)
        return {"evidence_id": event.id, "grade": asdict(result)}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app
