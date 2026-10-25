"""FastAPI surfaces for lessons, exercises, and evidence."""

from __future__ import annotations

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
from testbridge.exercise.grading import grade, kind_for_exercise
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore
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


def create_app(pack_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    pack_path = pack_dir or ROOT / "content-packs" / "sample-sensors"
    database = db_path or ROOT / "data" / "testbridge.db"
    pack = load_pack(pack_path)
    store = EvidenceStore(database)
    learning_store = LearningStore(database)
    learning = LearningService(pack, store, learning_store)

    app = FastAPI(title="TestBridge")
    app.state.pack = pack
    app.state.store = store
    app.state.learning = learning

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
        return {"request": request, "pack": pack, "learning": learning, **kwargs}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        modules = sorted(pack.modules.values(), key=lambda item: (item.order, item.id))
        lessons_by_module = {
            module.id: [pack.lessons[item] for item in module.lessons if item in pack.lessons]
            for module in modules
        }
        views = learning.all_mastery()
        weakest = sorted(views.values(), key=lambda item: item.estimate)[:3]
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=ctx(
                request,
                modules=modules,
                lessons_by_module=lessons_by_module,
                readiness=learning.readiness(),
                plan=learning.today_plan(),
                due_count=len(learning.due_reviews()),
                weakest=weakest,
            ),
        )

    @app.get("/lesson/{lesson_id}", response_class=HTMLResponse)
    def lesson_page(request: Request, lesson_id: str):
        if lesson_id not in pack.lessons:
            raise HTTPException(status_code=404, detail="lesson not found")
        view = render_lesson(pack, lesson_id)
        return templates.TemplateResponse(
            request=request,
            name="lesson.html",
            context=ctx(request, view=view),
        )

    @app.get("/progress", response_class=HTMLResponse)
    def progress_page(request: Request, concept: str = ""):
        events = store.list(concept_id=concept or None, limit=200)
        return templates.TemplateResponse(
            request=request,
            name="progress.html",
            context=ctx(
                request,
                events=events,
                selected=concept,
                total=store.count(),
                readiness=learning.readiness(),
                views=learning.all_mastery(),
            ),
        )

    @app.get("/today", response_class=HTMLResponse)
    def today_page(request: Request):
        plan = learning.today_plan()
        return templates.TemplateResponse(
            request=request, name="today.html", context=ctx(request, plan=plan)
        )

    @app.get("/concepts", response_class=HTMLResponse)
    def concepts_page(request: Request):
        views = learning.all_mastery()
        due = learning.due_reviews()
        due_counts: dict[str, int] = {}
        for review in due:
            for concept_id in review.concept_ids:
                due_counts[concept_id] = due_counts.get(concept_id, 0) + 1
        lesson_for_concept = {}
        for lesson in pack.lessons_in_order():
            for concept_id in lesson.manifest.concepts:
                lesson_for_concept.setdefault(concept_id, lesson.manifest.id)
        return templates.TemplateResponse(
            request=request, name="concepts.html",
            context=ctx(
                request, views=views, due_counts=due_counts,
                lesson_for_concept=lesson_for_concept,
            ),
        )

    @app.get("/review", response_class=HTMLResponse)
    def review_page(request: Request):
        due = learning.due_reviews()
        rows = []
        for review in due:
            lesson_id = next(
                (
                    lesson.manifest.id
                    for lesson in pack.lessons_in_order()
                    if review.exercise_id in lesson.manifest.exercises
                ),
                None,
            )
            rows.append({"review": review, "lesson_id": lesson_id})
        return templates.TemplateResponse(
            request=request, name="review.html", context=ctx(request, rows=rows)
        )

    @app.post("/api/evidence")
    def submit_evidence(payload: EvidenceRequest):
        lesson = pack.lessons.get(payload.lesson_id)
        if lesson is None:
            raise HTTPException(status_code=404, detail="lesson not found")
        exercise = pack.exercises.get(payload.exercise_id)
        if exercise is None:
            raise HTTPException(status_code=404, detail="exercise not found")
        if payload.exercise_id not in lesson.manifest.exercises:
            raise HTTPException(status_code=400, detail="exercise not in lesson")
        result = grade(exercise, payload.response)
        event = new_event(
            kind=kind_for_exercise(exercise.type),
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
        learning.record(event)
        return {"evidence_id": event.id, "grade": asdict(result)}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app
