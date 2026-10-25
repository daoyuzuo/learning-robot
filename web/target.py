"""Target JD pages mounted onto the main app (P4.2)."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from testbridge.career.jd import (
    JdError,
    JdSuggestion,
    MAX_TARGET_ROLE_CHARS,
    manual_suggestion,
    parse_suggestion,
    parse_with_llm,
    safe_text,
    suggest_weights,
    validate_jd_text,
)
from testbridge.career.matching import build_report
from testbridge.career.store import TargetJd, TargetJdStore
from testbridge.content.repository import ContentPack
from testbridge.learning.service import LearningService
from testbridge.tutor.client import (
    LlmClient,
    TutorTimeoutError,
    TutorUpstreamError,
)
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

    def uncovered_texts(suggestion: JdSuggestion) -> list[str]:
        return [
            item.text for item in suggestion.requirements if not item.concepts
        ]

    def review_context(
        request: Request,
        *,
        source_text: str,
        suggestion: JdSuggestion,
        weights: dict[str, float],
    ):
        goal = learning.goal()
        preview_goal = replace(goal, concept_overrides=weights)
        report = build_report(
            pack, preview_goal, learning.all_mastery(),
            uncovered=uncovered_texts(suggestion),
        )
        requirement_texts = {
            concept_id: [
                item.text for item in suggestion.requirements
                if concept_id in item.concepts
            ]
            for concept_id in pack.concepts
        }
        rationale_texts = {
            concept_id: next(
                (item.rationale for item in suggestion.requirements
                 if concept_id in item.concepts and item.rationale),
                "",
            )
            for concept_id in pack.concepts
        }
        rows = [
            {
                "id": concept_id,
                "title": concept.title,
                "target_level": concept.target_level,
                "current_weight": goal.concept_overrides.get(concept_id, 1.0),
                "suggested": weights.get(concept_id, 1.0),
                "requirements": requirement_texts[concept_id],
                "rationale": rationale_texts[concept_id],
            }
            for concept_id, concept in sorted(pack.concepts.items())
        ]
        removed = sorted(
            cid for cid in goal.concept_overrides if cid not in weights
        )
        unmapped = [
            item for item in suggestion.requirements if not item.concepts
        ]
        return ctx(
            request,
            source_text=source_text,
            suggestion=suggestion,
            rows=rows,
            removed=removed,
            unmapped=unmapped,
            report=report,
            requirements_json=json.dumps(
                [asdict(item) for item in suggestion.requirements],
                ensure_ascii=False,
            ),
        )

    @router.post("/target/parse", response_class=HTMLResponse)
    def target_parse(request: Request, jd_text: str = Form("")):
        try:
            text = validate_jd_text(jd_text)
        except JdError as exc:
            return templates.TemplateResponse(
                request=request,
                name="target_review.html",
                status_code=400,
                context=ctx(
                    request, source_text=jd_text, suggestion=None,
                    rows=[], removed=[], unmapped=[], report=None,
                    requirements_json="[]", error=str(exc),
                ),
            )
        try:
            suggestion = parse_with_llm(llm, config, pack, text)
        except (TutorTimeoutError, TutorUpstreamError):
            suggestion = manual_suggestion(
                note="模型服务不可用，请手动设置权重。"
            )
        weights = suggest_weights(suggestion)
        return templates.TemplateResponse(
            request=request,
            name="target_review.html",
            context=review_context(
                request, source_text=text, suggestion=suggestion,
                weights=weights,
            ),
        )

    @router.post("/target/confirm")
    async def target_confirm(request: Request):
        form = await request.form()
        source_text = str(form.get("source_text") or "")
        target_role = str(form.get("target_role") or "")
        requirements_json = str(form.get("requirements_json") or "[]")
        model = str(form.get("model") or "")[:100] or None
        try:
            text = validate_jd_text(source_text)
            raw_requirements = json.loads(requirements_json)
            if not isinstance(raw_requirements, list):
                raise JdError("requirements 必须是数组")
            if raw_requirements:
                suggestion = parse_suggestion(
                    json.dumps(
                        {"target_role": target_role,
                         "requirements": raw_requirements},
                        ensure_ascii=False,
                    ),
                    pack=pack,
                    model=model,
                )
            else:
                suggestion = JdSuggestion(
                    target_role=safe_text(target_role.strip())[
                        :MAX_TARGET_ROLE_CHARS
                    ],
                    requirements=(),
                    mode="manual",
                    model=model,
                )
        except (JdError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        weights: dict[str, float] = {}
        for concept_id in pack.concepts:
            raw = form.get(f"weight_{concept_id}")
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400, detail=f"权重非法：{concept_id}"
                ) from exc
            if not math.isfinite(value) or not 1.0 <= value <= 2.0:
                raise HTTPException(
                    status_code=400,
                    detail=f"权重必须在 1.0–2.0：{concept_id}",
                )
            if abs(value * 10 - round(value * 10)) > 1e-9:
                raise HTTPException(
                    status_code=400,
                    detail=f"权重必须是 0.1 的倍数：{concept_id}",
                )
            if value > 1.0:
                weights[concept_id] = value

        store.save(TargetJd(
            learner_id=learner_id,
            source_text=text,
            target_role=suggestion.target_role,
            requirements=[asdict(item) for item in suggestion.requirements],
            weights=weights,
            model=model,
        ))
        goal = learning.goal()
        learning.store.set_goal(replace(
            goal,
            target_role=suggestion.target_role or goal.target_role,
            concept_overrides=weights,
        ))
        return RedirectResponse("/target", status_code=303)

    app.state.target_store = store
    app.include_router(router)
