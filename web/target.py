"""Target JD pages mounted onto the main app (P4.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from testbridge.career.matching import build_report
from testbridge.career.store import TargetJdStore
from testbridge.content.repository import ContentPack
from testbridge.learning.service import LearningService
from testbridge.tutor.client import LlmClient
from testbridge.tutor.config import TutorConfig


def mount_target(
    app,
    templates,
    *,
    pack: ContentPack,
    learning: LearningService,
    store: TargetJdStore,
    config: TutorConfig | None = None,
    llm: LlmClient | None = None,
    learner_id: str = "local",
) -> None:
    router = APIRouter()

    def ctx(request: Request, **kwargs):
        return {"request": request, "pack": pack, **kwargs}

    @router.get("/target", response_class=HTMLResponse)
    def target_page(request: Request):
        target = store.get(learner_id)
        report = None
        if target is not None:
            report = build_report(
                pack, learning.goal(), learning.all_mastery(),
                uncovered=[
                    item.get("text", "")
                    for item in target.requirements
                    if not item.get("concepts")
                ],
            )
        return templates.TemplateResponse(
            request=request,
            name="target.html",
            context=ctx(request, target=target, report=report, error=None),
        )

    app.state.target_store = store
    app.include_router(router)
