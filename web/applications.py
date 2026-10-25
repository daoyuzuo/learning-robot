"""Job application pages mounted onto the main app (P4.3)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from testbridge.career.applications import (
    STATUSES,
    ApplicationError,
    ApplicationStore,
)


def mount_applications(
    app, templates, *, store: ApplicationStore, learner_id: str = "local"
) -> None:
    router = APIRouter()

    def ctx(request: Request, **kwargs):
        return {
            "request": request,
            "statuses": STATUSES,
            "today": date.today().isoformat(),
            **kwargs,
        }

    def render_list(request: Request, *, status_code: int = 200,
                    error: str | None = None, form: dict | None = None,
                    selected: str = ""):
        return templates.TemplateResponse(
            request=request,
            name="applications.html",
            status_code=status_code,
            context=ctx(
                request,
                items=store.list(learner_id, status=selected or None),
                due=store.due(date.today().isoformat(), learner_id),
                counts=store.counts(learner_id),
                selected=selected,
                error=error,
                form=form or {},
            ),
        )

    @router.get("/applications", response_class=HTMLResponse)
    def applications_page(request: Request, status: str = ""):
        selected = status if status in STATUSES else ""
        return render_list(request, selected=selected)

    @router.post("/applications")
    def applications_create(
        request: Request,
        company: str = Form(""),
        role: str = Form(""),
        source: str = Form(""),
        status: str = Form("draft"),
        applied_at: str = Form(""),
        next_action_at: str = Form(""),
        next_action: str = Form(""),
        notes: str = Form(""),
    ):
        try:
            application = store.create(
                company=company, role=role, source=source, status=status,
                applied_at=applied_at, next_action_at=next_action_at,
                next_action=next_action, notes=notes, learner_id=learner_id,
            )
        except ApplicationError as exc:
            return render_list(
                request, status_code=400, error=str(exc),
                form={
                    "company": company, "role": role, "source": source,
                    "status": status, "applied_at": applied_at,
                    "next_action_at": next_action_at,
                    "next_action": next_action, "notes": notes,
                },
            )
        return RedirectResponse(
            f"/applications/{application.id}", status_code=303
        )

    app.state.application_store = store
    app.include_router(router)
