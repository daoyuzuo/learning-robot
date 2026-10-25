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
from testbridge.tutor.client import LlmClient
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

    app.include_router(router)
