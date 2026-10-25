"""Job application pages mounted onto the main app (P4.3)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from testbridge.career.applications import (
    STATUS_LABELS,
    STATUSES,
    TERMINAL_STATUSES,
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
            "status_labels": STATUS_LABELS,
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

    def application_or_404(app_id: str):
        application = store.get(app_id, learner_id)
        if application is None:
            raise HTTPException(status_code=404, detail="投递记录不存在")
        return application

    def render_detail(
        request: Request, application, *, status_code: int = 200,
        error: str | None = None, form: dict | None = None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="application_detail.html",
            status_code=status_code,
            context=ctx(
                request,
                application=application,
                error=error,
                form=form or {},
                terminal=application.status in TERMINAL_STATUSES,
            ),
        )

    @router.get("/applications/{app_id}", response_class=HTMLResponse)
    def application_detail(request: Request, app_id: str):
        return render_detail(request, application_or_404(app_id))

    @router.post("/applications/{app_id}")
    def application_update(
        request: Request,
        app_id: str,
        company: str = Form(""),
        role: str = Form(""),
        source: str = Form(""),
        status: str = Form("draft"),
        applied_at: str = Form(""),
        next_action_at: str = Form(""),
        next_action: str = Form(""),
        notes: str = Form(""),
    ):
        current = application_or_404(app_id)
        try:
            store.update(
                app_id, learner_id=learner_id,
                company=company, role=role, source=source, status=status,
                applied_at=applied_at, next_action_at=next_action_at,
                next_action=next_action, notes=notes,
            )
        except ApplicationError as exc:
            return render_detail(
                request, current, status_code=400, error=str(exc),
                form={
                    "company": company, "role": role, "source": source,
                    "status": status, "applied_at": applied_at,
                    "next_action_at": next_action_at,
                    "next_action": next_action, "notes": notes,
                },
            )
        return RedirectResponse(f"/applications/{app_id}", status_code=303)

    @router.post("/applications/{app_id}/withdraw")
    def application_withdraw(request: Request, app_id: str):
        application_or_404(app_id)
        store.withdraw(app_id, learner_id)
        return RedirectResponse(f"/applications/{app_id}", status_code=303)

    app.state.application_store = store
    app.include_router(router)
