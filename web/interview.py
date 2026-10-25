"""Interview pages and JSON API mounted onto the main app."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceStore
from testbridge.interview.bank import (
    InterviewBank,
    InterviewBankError,
    load_bank,
    resolve_bank_path,
)
from testbridge.interview.session import InterviewService, SessionError
from testbridge.interview.store import InterviewStore
from testbridge.learning.service import LearningService
from testbridge.tutor.client import LlmClient, TutorTimeoutError, TutorUpstreamError
from testbridge.tutor.config import TutorConfig


def mount_interview(
    app,
    templates,
    *,
    pack: ContentPack,
    banks_root: Path,
    store: InterviewStore,
    evidence_store: EvidenceStore,
    learning: LearningService,
    config: TutorConfig | None = None,
    llm: LlmClient | None = None,
    learner_id: str = "local",
) -> None:
    path = resolve_bank_path(pack.root, pack.meta.id, banks_root)
    bank: InterviewBank | None = None
    bank_error: str | None = None
    if path is None:
        bank_error = f"未找到 {pack.meta.id} 的面试题库。"
    else:
        try:
            bank = load_bank(
                path, pack_id=pack.meta.id, concept_ids=set(pack.concepts)
            )
        except InterviewBankError as exc:
            bank_error = str(exc)

    service = (
        InterviewService(
            pack, bank, store, evidence_store, learning,
            llm=llm, config=config, learner_id=learner_id,
        )
        if bank is not None else None
    )
    app.state.interview = service
    app.state.interview_bank_error = bank_error
    templates.env.globals["interview_available"] = lambda: bank is not None

    router = APIRouter()

    def ctx(request: Request, **kwargs):
        return {
            "request": request,
            "pack": pack,
            "bank_error": bank_error,
            **kwargs,
        }

    def weak_preview() -> list[dict]:
        if bank is None:
            return []
        views = learning.all_mastery()
        ids = [
            cid for cid in bank.concepts_with_questions()
            if cid in pack.concepts
        ]
        rows = [
            {
                "id": cid,
                "title": pack.concepts[cid].title,
                "estimate": views[cid].estimate if cid in views else 0.0,
            }
            for cid in ids
        ]
        return sorted(rows, key=lambda row: (row["estimate"], row["id"]))[:3]

    @router.get("/interview", response_class=HTMLResponse)
    def interview_start(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="interview_start.html",
            context=ctx(
                request,
                weak=weak_preview(),
                sessions=store.list_sessions(learner_id, limit=5),
                concepts=[
                    {"id": cid, "title": pack.concepts[cid].title}
                    for cid in (bank.concepts_with_questions() if bank else [])
                    if cid in pack.concepts
                ],
            ),
        )

    @router.post("/interview")
    def interview_create(
        question_count: int = Form(3),
        concepts: list[str] = Form(default=[]),  # noqa: B008 - FastAPI requires the call here
    ):
        if service is None:
            raise HTTPException(status_code=503, detail="面试题库不可用")
        try:
            session = service.start(
                question_count, concept_ids=concepts or None
            )
        except (SessionError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            f"/interview/session/{session.id}", status_code=303
        )

    def session_or_404(session_id: str):
        if service is None:
            raise HTTPException(status_code=503, detail="面试题库不可用")
        try:
            return service.get(session_id)
        except SessionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/interview/session/{session_id}", response_class=HTMLResponse)
    def interview_session(request: Request, session_id: str):
        session = session_or_404(session_id)
        if session.status == "completed":
            return RedirectResponse(
                f"/interview/session/{session_id}/summary", status_code=303
            )
        answers = service.answers(session_id)
        index = min(session.current_index, len(session.question_ids) - 1)
        question_id = session.question_ids[index]
        question = bank.by_id(question_id)
        answer = answers.get(question_id)
        return templates.TemplateResponse(
            request=request,
            name="interview_session.html",
            context=ctx(
                request,
                session=session,
                index=index,
                total=len(session.question_ids),
                question=question,
                answer=answer,
                status=session.status,
            ),
        )

    @router.put("/api/interview/session/{session_id}/answer")
    def save_answer(session_id: str, payload: dict):
        session_or_404(session_id)
        try:
            service.save_draft(
                session_id,
                str(payload.get("question_id") or ""),
                str(payload.get("answer") or ""),
            )
        except SessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @router.post("/api/interview/session/{session_id}/grade")
    def grade_answer(session_id: str, payload: dict):
        session_or_404(session_id)
        try:
            suggestion = service.grade(
                session_id, str(payload.get("question_id") or "")
            )
        except SessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (TutorTimeoutError, TutorUpstreamError) as exc:
            raise HTTPException(
                status_code=502, detail="模型服务不可用，请重试"
            ) from exc
        return {
            "mode": suggestion.mode,
            "scores": [
                {
                    "dimension": item.dimension,
                    "weight": item.weight,
                    "score": item.score,
                    "rationale": item.rationale,
                }
                for item in suggestion.scores
            ],
            "summary": suggestion.summary,
            "strengths": suggestion.strengths,
            "gaps": suggestion.gaps,
        }

    @router.post("/api/interview/session/{session_id}/reset")
    def reset_answer(session_id: str, payload: dict):
        session_or_404(session_id)
        try:
            service.reset_answer(
                session_id, str(payload.get("question_id") or "")
            )
        except SessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @router.post("/api/interview/session/{session_id}/abandon")
    def abandon_session(session_id: str, payload: dict | None = None):
        session_or_404(session_id)
        service.abandon(session_id)
        return {"ok": True}

    app.include_router(router)
