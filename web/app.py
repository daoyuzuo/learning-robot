"""FastAPI surfaces for lessons, exercises, and evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from testbridge.artifact import ArtifactError, save_artifact
from testbridge.concept_graph import prerequisite_svg
from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.exercise.grading import grade, kind_for_exercise
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore
from testbridge.lesson.renderer import render_exercise_form, render_lesson
from testbridge.readiness import LEVEL_ORDER
from testbridge.sync import export_state, import_state, resolve_state_dir
from testbridge.tutor.client import (
    OpenAICompatibleClient,
    TutorTimeoutError,
    TutorUpstreamError,
)
from testbridge.tutor.config import TutorConfig, load_config, missing_vars
from testbridge.tutor.context import build_context
from testbridge.tutor.review_service import (
    EvidenceNotFoundError,
    ReviewService,
    UnsupportedEvidenceError,
)
from testbridge.tutor.review_store import ExerciseReviewStore
from testbridge.tutor.service import (
    InvalidQuestionError,
    LessonNotFoundError,
    TutorService,
)
from testbridge.tutor.store import TutorStore

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


def _snapshot_hook(
    database: Path,
    snapshot: Path | None,
    status: dict[str, Any],
) -> Any:
    """Mirror every new evidence row into the committable snapshot.

    Failures are recorded on ``app.state.sync_status`` and surfaced on
    ``/progress``: a read-only checkout must still accept answers.
    """
    if snapshot is None:
        return None

    def mirror(_event) -> None:
        try:
            export_state(database, snapshot)
        except OSError as exc:
            status["error"] = f"快照写入失败：{exc}"

    return mirror


class EvidenceRequest(BaseModel):
    lesson_id: str
    exercise_id: str
    response: Any = None
    hints_used: int = 0
    duration_ms: int = 0
    session_id: str | None = None


class TutorRequest(BaseModel):
    lesson_id: str
    anchor: str = ""
    question: str
    web: bool = True
    selection: str = ""


class ReviewRequest(BaseModel):
    evidence_id: str
    refresh: bool = False


def create_app(
    pack_dir: Path | None = None,
    db_path: Path | None = None,
    tutor: TutorService | None = None,
    reviewer: ReviewService | None = None,
    artifacts_dir: Path | None = None,
    interview_banks: Path | None = None,
    interview_llm=None,
    interview_config: TutorConfig | None = None,
    target_llm=None,
    target_config: TutorConfig | None = None,
    state_dir: str | Path | None = None,
) -> FastAPI:
    if pack_dir is None:
        raise ValueError("请指定课程包目录，例如 tb serve content-packs/<id>")
    pack_path = pack_dir
    database = db_path or ROOT / "data" / "testbridge.db"
    uploads = artifacts_dir or ROOT / "data" / "artifacts"
    pack = load_pack(pack_path)
    snapshot = resolve_state_dir(database, state_dir)
    sync_status: dict[str, Any] = {"state_dir": snapshot, "error": None, "imported": 0}
    store = EvidenceStore(database, on_append=_snapshot_hook(database, snapshot, sync_status))
    learning_store = LearningStore(database)
    learning = LearningService(pack, store, learning_store)

    # Merge the committed snapshot first, then replay it into mastery/review.
    # A broken or unwritable snapshot must never stop the app from starting.
    if snapshot is not None:
        try:
            reported = import_state(database, snapshot)
            sync_status["imported"] = reported.imported
            if reported.imported:
                rebuild_state(learning)
        except (OSError, ValueError) as exc:
            sync_status["error"] = f"导入失败：{exc}"

    config = load_config()
    tutor_search = None
    if tutor is None and config is not None and config.search_enabled:
        from testbridge.search import DeepSeekSearch

        tutor_search = DeepSeekSearch(config)

    if (tutor is None or reviewer is None) and config is not None:
        client = OpenAICompatibleClient(config)
        if tutor is None:
            tutor = TutorService(
                pack, TutorStore(database), client, config, search=tutor_search
            )
        if reviewer is None:
            reviewer = ReviewService(
                pack, store, ExerciseReviewStore(database), client, config
            )

    app = FastAPI(title="TestBridge")
    app.state.pack = pack
    app.state.store = store
    app.state.learning = learning
    app.state.tutor = tutor
    app.state.reviewer = reviewer
    app.state.state_dir = snapshot
    app.state.sync_status = sync_status

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'"
        )
        return response

    templates = Jinja2Templates(directory=str(BASE / "templates"))

    from testbridge.icons import icon_markup
    from web.labels import register as register_labels

    register_labels(templates)
    templates.env.globals["icon_svg"] = icon_markup

    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    assets_dir = pack.root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    from testbridge.interview.store import InterviewStore
    from web.interview import mount_interview

    mount_interview(
        app,
        templates,
        pack=pack,
        banks_root=interview_banks or ROOT / "interview-banks",
        store=InterviewStore(database),
        evidence_store=store,
        learning=learning,
        config=interview_config if interview_config is not None else config,
        llm=interview_llm,
    )

    from testbridge.career.store import TargetJdStore
    from web.target import mount_target

    mount_target(
        app,
        templates,
        pack=pack,
        learning=learning,
        store=TargetJdStore(database),
        config=target_config if target_config is not None else config,
        llm=target_llm,
    )

    from testbridge.career.applications import ApplicationStore
    from web.applications import mount_applications

    mount_applications(
        app, templates, store=ApplicationStore(database),
    )

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
        readiness = learning.readiness(views)
        plan = learning.today_plan(views)
        concept_titles = {cid: item.title for cid, item in pack.concepts.items()}
        lesson_titles = {lid: item.manifest.title for lid, item in pack.lessons.items()}
        mastered = sum(
            1
            for view in views.values()
            if view.concept_id in pack.concepts
            and LEVEL_ORDER[view.level]
            >= LEVEL_ORDER[pack.concepts[view.concept_id].target_level]
        )
        module_rows = []
        for module in modules:
            concepts = [cid for cid in module.concepts if cid in pack.concepts]
            done = sum(
                1
                for cid in concepts
                if views.get(cid) is not None
                and LEVEL_ORDER[views[cid].level] >= LEVEL_ORDER[pack.concepts[cid].target_level]
            )
            module_rows.append({
                "module": module,
                "lessons": lessons_by_module[module.id],
                "done": done,
                "concepts": len(concepts),
            })
        total_minutes = sum(
            lesson.manifest.minutes
            for lessons in lessons_by_module.values()
            for lesson in lessons
        )
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=ctx(
                request,
                modules=modules,
                lessons_by_module=lessons_by_module,
                module_rows=module_rows,
                concept_titles=concept_titles,
                lesson_titles=lesson_titles,
                readiness=readiness,
                plan=plan,
                due_count=len(learning.due_reviews()),
                weakest=weakest,
                concept_total=len(pack.concepts),
                mastered_count=mastered,
                lesson_total=len(pack.lessons),
                total_minutes=total_minutes,
            ),
        )

    @app.get("/lesson/{lesson_id}", response_class=HTMLResponse)
    def lesson_page(request: Request, lesson_id: str):
        if lesson_id not in pack.lessons:
            raise HTTPException(status_code=404, detail="lesson not found")
        view = render_lesson(pack, lesson_id)
        headings = build_context(pack, lesson_id).headings
        ordered = pack.lessons_in_order()
        position = next(
            (
                index
                for index, item in enumerate(ordered, start=1)
                if item.manifest.id == lesson_id
            ),
            1,
        )
        return templates.TemplateResponse(
            request=request,
            name="lesson.html",
            context=ctx(
                request,
                view=view,
                tutor=tutor,
                tutor_missing=missing_vars() if tutor is None else [],
                tutor_web=bool(tutor and getattr(tutor, "web_available", False)),
                tutor_headings=headings,
                tutor_history=tutor.history(lesson_id) if tutor else [],
                lesson_position={"index": position, "total": len(ordered)},
            ),
        )

    @app.get("/progress", response_class=HTMLResponse)
    def progress_page(request: Request, concept: str = ""):
        events = store.list(concept_id=concept or None, limit=200)
        views = learning.all_mastery()
        lesson_titles = {lid: item.manifest.title for lid, item in pack.lessons.items()}
        exercise_prompts = {eid: item.prompt for eid, item in pack.exercises.items()}
        return templates.TemplateResponse(
            request=request,
            name="progress.html",
            context=ctx(
                request,
                events=events,
                selected=concept,
                total=store.count(),
                filtered_total=store.count(concept_id=concept) if concept else 0,
                readiness=learning.readiness(views),
                views=views,
                lesson_titles=lesson_titles,
                exercise_prompts=exercise_prompts,
                sync_status=sync_status,
            ),
        )

    @app.get("/today", response_class=HTMLResponse)
    def today_page(request: Request):
        plan = learning.today_plan()
        lesson_titles = {lid: item.manifest.title for lid, item in pack.lessons.items()}
        return templates.TemplateResponse(
            request=request,
            name="today.html",
            context=ctx(request, plan=plan, lesson_titles=lesson_titles),
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
        concept_titles = {cid: item.title for cid, item in pack.concepts.items()}
        prereq_titles = {
            cid: [concept_titles.get(p, p) for p in item.prerequisites]
            for cid, item in pack.concepts.items()
        }
        return templates.TemplateResponse(
            request=request, name="concepts.html",
            context=ctx(
                request, views=views, due_counts=due_counts,
                lesson_for_concept=lesson_for_concept,
                concept_titles=concept_titles,
                prereq_titles=prereq_titles,
                graph=prerequisite_svg(pack, views),
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
        concept_titles = {cid: item.title for cid, item in pack.concepts.items()}
        exercise_prompts = {eid: item.prompt for eid, item in pack.exercises.items()}
        return templates.TemplateResponse(
            request=request, name="review.html",
            context=ctx(
                request, rows=rows,
                concept_titles=concept_titles,
                exercise_prompts=exercise_prompts,
            ),
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

    @app.get("/review/session", response_class=HTMLResponse)
    def review_session(request: Request):
        lessons = pack.lessons_in_order()
        cards = []
        skipped = 0
        for review in learning.due_reviews():
            exercise = pack.exercises.get(review.exercise_id)
            lesson_id = next(
                (
                    lesson.manifest.id
                    for lesson in lessons
                    if review.exercise_id in lesson.manifest.exercises
                ),
                None,
            )
            if exercise is None or lesson_id is None:
                skipped += 1
                continue
            cards.append({
                "exercise_id": exercise.id,
                "lesson_id": lesson_id,
                "lesson_title": pack.lessons[lesson_id].manifest.title,
                "concept_titles": [
                    pack.concepts[item].title
                    for item in review.concept_ids
                    if item in pack.concepts
                ],
                "form": render_exercise_form(exercise, lesson_id),
            })
        return templates.TemplateResponse(
            request=request,
            name="review_session.html",
            context=ctx(request, cards=cards, skipped=skipped),
        )

    @app.post("/api/review")
    def review_evidence(payload: ReviewRequest):
        if reviewer is None:
            raise HTTPException(
                status_code=503,
                detail={"code": "tutor_disabled", "message": "未配置模型服务"},
            )
        try:
            reply = reviewer.review(payload.evidence_id, payload.refresh)
        except EvidenceNotFoundError:
            raise HTTPException(
                status_code=404,
                detail={"code": "evidence_not_found", "message": "作答不存在"},
            ) from None
        except UnsupportedEvidenceError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "unsupported_evidence", "message": str(exc)},
            ) from None
        except TutorTimeoutError:
            raise HTTPException(
                status_code=504,
                detail={"code": "tutor_timeout", "message": "模型服务超时"},
            ) from None
        except TutorUpstreamError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "tutor_upstream", "message": str(exc)},
            ) from None

        if reply.evidence_event is not None:
            store.append(reply.evidence_event)
            learning.record(reply.evidence_event)

        review = reply.review
        return {
            "verdict": review.verdict,
            "explanation": review.explanation,
            "strengths": review.strengths,
            "gaps": review.gaps,
            "rubric": [
                {"dimension": item.dimension, "met": item.met,
                 "comment": item.comment}
                for item in review.rubric
            ],
            "suggested_score": review.suggested_score,
            "model": reviewer.config.model,
            "cached": reply.cached,
            "saved": reply.saved,
        }

    @app.post("/api/tutor")
    def ask_tutor(payload: TutorRequest):
        if tutor is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "tutor_disabled",
                    "message": "未配置模型服务",
                    "missing": missing_vars(),
                },
            )
        try:
            reply = tutor.ask(
                payload.lesson_id, payload.anchor, payload.question,
                use_web=payload.web,
                selection=payload.selection,
            )
        except LessonNotFoundError:
            raise HTTPException(
                status_code=404,
                detail={"code": "lesson_not_found", "message": "课程不存在"},
            ) from None
        except InvalidQuestionError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_question", "message": str(exc)},
            ) from None
        except TutorTimeoutError:
            raise HTTPException(
                status_code=504,
                detail={"code": "tutor_timeout", "message": "模型服务超时"},
            ) from None
        except TutorUpstreamError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "tutor_upstream", "message": str(exc)},
            ) from None
        return {
            "answer": reply.answer.answer,
            "basis": reply.answer.basis,
            "citations": reply.answer.citations,
            "followups": reply.answer.followups,
            "saved": reply.saved,
            "web_used": reply.web_used,
            "web_sources": reply.web_sources,
        }

    @app.post("/api/artifact")
    def upload_artifact(
        lesson_id: str = Form(...),
        exercise_id: str = Form(...),
        notes: str = Form(""),
        checked: str = Form("[]"),
        hints_used: int = Form(0),
        duration_ms: int = Form(0),
        file: UploadFile = File(...),  # noqa: B008 - FastAPI requires the call here
    ):
        lesson = pack.lessons.get(lesson_id)
        if lesson is None:
            raise HTTPException(status_code=404, detail="lesson not found")
        exercise = pack.exercises.get(exercise_id)
        if exercise is None:
            raise HTTPException(status_code=404, detail="exercise not found")
        if exercise_id not in lesson.manifest.exercises:
            raise HTTPException(status_code=400, detail="exercise not in lesson")
        if exercise.type != "artifact" or exercise.artifact is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "not_artifact", "message": "该练习不需要上传文件"},
            )

        try:
            selected = json.loads(checked) if checked else []
        except ValueError:
            selected = []
        if not isinstance(selected, list):
            selected = []

        evidence_id = uuid4().hex
        try:
            stored = save_artifact(
                uploads, evidence_id, file.filename or "", file.file.read(),
                exercise.artifact,
            )
        except ArtifactError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": exc.code, "message": exc.message},
            ) from None

        try:
            display_path = stored.path.relative_to(ROOT).as_posix()
        except ValueError:
            display_path = stored.path.as_posix()

        response = {"path": display_path, "notes": notes, "checked": selected}
        result = grade(exercise, response)
        event = replace(
            new_event(
                kind=kind_for_exercise(exercise.type),
                lesson_id=lesson_id,
                exercise_id=exercise_id,
                concept_ids=exercise.concepts,
                outcome=result.outcome,
                score=result.score,
                max_score=result.max_score,
                payload={
                    "response": response,
                    "filename": stored.filename,
                    "size": stored.size,
                    "hints_used": hints_used,
                    "duration_ms": duration_ms,
                    "feedback": result.feedback,
                    "details": result.details,
                },
                source="web",
            ),
            id=evidence_id,
        )
        store.append(event)
        learning.record(event)
        return {
            "evidence_id": event.id,
            "grade": asdict(result),
            "artifact_path": display_path,
        }

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app
