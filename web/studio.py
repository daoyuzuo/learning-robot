"""Content studio routes.

The studio is an authoring surface only: it never touches mastery, scheduling,
or evidence. Model output and search results are untrusted input.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from testbridge.quality.evaluate import QualityUnavailable
from testbridge.studio import lessons as lesson_writer
from testbridge.studio import outline as outline_writer
from testbridge.studio import research as research_runner
from testbridge.studio.evolution import (
    EvolutionBusy,
    EvolutionJob,
    compare_snapshots,
    draft_quality,
    list_snapshots,
    save_snapshot,
    snapshot_lesson,
    timestamp_now,
)
from testbridge.studio.gates import (
    PromoteError,
    promote,
    quality_draft,
    validate_draft,
    verify_resources,
)
from testbridge.studio.jobs import JobBusy, JobRunner
from testbridge.studio.lessons import DEFAULT_MODULE_ID, LessonError
from testbridge.studio.outline import (
    OutlineError,
    flatten_modules,
    parse_outline_html,
    render_lesson_outline,
    save_outline_html,
    write_outline,
)
from testbridge.studio.prompts import (
    LESSON_SYSTEM,
    OUTLINE_SYSTEM,
    render_concepts_text,
    render_lesson_prompt,
    render_outline_prompt,
)
from testbridge.studio.research import (
    preflight_urls,
    render_research_for_prompt,
    usable_urls_from_payload,
)
from testbridge.studio.search import SearchProvider
from testbridge.studio.search_router import SearchRoute, SearchRouter
from testbridge.studio.store import ID_RE, DraftError, DraftStore
from testbridge.studio.version import PROMPT_VERSION
from testbridge.tutor.client import LlmClient
from testbridge.tutor.config import TutorConfig, missing_vars

LEVELS = {"L1", "L2", "L3", "L4"}


class OutlineBody(BaseModel):
    html: str


class EvolutionTarget(BaseModel):
    draft_id: str
    lesson_id: str


class EvolutionBody(BaseModel):
    # Empty default so a body without ``targets`` is a 400 invalid_request
    # from the route, not a framework-level 422.
    targets: list[EvolutionTarget] = Field(default_factory=list)


def _snapshot_summary(snapshot: dict) -> dict:
    """Return the fields the evolution UI compares, without the raw HTML."""
    metrics = snapshot.get("metrics") or {}
    return {
        "prompt_version": snapshot.get("prompt_version"),
        "exercise_count": metrics.get("exercise_count", 0),
        "types": list(metrics.get("types") or []),
        "max_level": metrics.get("max_level", ""),
        "resource_count": metrics.get("resource_count", 0),
        "trust": dict(metrics.get("trust") or {}),
    }


def mount_studio(
    app,
    templates,
    *,
    drafts_root: Path,
    packs_root: Path,
    config: TutorConfig | None,
    llm: LlmClient | None,
    search: SearchProvider | SearchRouter | None,
    inline: bool = False,
    url_checker=None,
) -> None:
    store = DraftStore(drafts_root)
    store.mark_interrupted()
    runner = JobRunner(store, inline=inline)
    evolution = EvolutionJob(store, runner)
    app.state.studio_store = store
    app.state.evolution = evolution
    app.state.studio_llm = llm
    app.state.studio_search = search
    app.state.studio_url_checker = url_checker
    router = APIRouter()

    def ctx(request: Request, **kwargs):
        return {
            "request": request,
            "missing": missing_vars(),
            "enabled": config is not None and llm is not None and search is not None,
            **kwargs,
        }

    def require_enabled() -> None:
        if config is None or llm is None or search is None:
            raise HTTPException(
                status_code=503,
                detail={"code": "tutor_disabled", "message": "未配置模型服务"},
            )

    def draft_or_404(draft_id: str) -> dict:
        if not store.exists(draft_id):
            raise HTTPException(
                status_code=404,
                detail={"code": "draft_not_found", "message": "草稿不存在"},
            )
        return store.load(draft_id)

    def _yaml(draft_id: str, relative: str) -> dict:
        try:
            data = yaml.safe_load(store.read(draft_id, relative))
        except FileNotFoundError:
            return {}
        return data if isinstance(data, dict) else {}

    def concepts(draft_id: str) -> list[dict]:
        return list(_yaml(draft_id, "concepts.yaml").get("concepts") or [])

    def concepts_text(
        draft_id: str, selected: list[str] | None = None
    ) -> str:
        draft = store.load(draft_id)
        items = concepts(draft_id)
        if selected:
            wanted = set(selected)
            items = [item for item in items if item.get("id") in wanted]
        return render_concepts_text(draft.get("level") or "L2", items)

    def route_for(draft: dict, titles: list[str], domains: list[str]) -> SearchRoute:
        if hasattr(search, "route"):
            return search.route(
                str(draft.get("search_backend") or "auto"),
                topic=str(draft.get("topic") or ""),
                concept_titles=titles,
                concept_domains=domains,
            )
        return SearchRoute("custom", search)

    def route_for_query(
        draft: dict, titles: list[str], domains: list[str], kind: str
    ) -> SearchRoute:
        backend = str(draft.get("search_backend") or "auto")
        if hasattr(search, "route_query"):
            return search.route_query(
                backend, kind,
                topic=str(draft.get("topic") or ""),
                concept_titles=titles,
                concept_domains=domains,
            )
        return route_for(draft, titles, domains)

    def outline_modules(draft_id: str) -> list:
        try:
            return parse_outline_html(store.read(draft_id, "outline.html"))
        except (FileNotFoundError, OutlineError):
            return []

    def outline_plans(draft_id: str) -> list:
        return flatten_modules(outline_modules(draft_id))

    def add_usage(draft_id: str, *, searches: int = 0, llm_calls: int = 0) -> None:
        draft = store.load(draft_id)
        usage = draft.setdefault("usage", {"searches": 0, "llm_calls": 0})
        usage["searches"] = int(usage.get("searches") or 0) + searches
        usage["llm_calls"] = int(usage.get("llm_calls") or 0) + llm_calls
        store.save(draft)

    def generate(draft_id: str, system: str, prompt: str, parse):
        """Call the model, retrying once with the validation error attached."""
        calls = 0
        for attempt in range(2):
            calls += 1
            raw = llm.complete(system, prompt)
            try:
                result = parse(raw)
            except (OutlineError, LessonError) as exc:
                if attempt == 1:
                    add_usage(draft_id, llm_calls=calls)
                    raise
                prompt = (
                    prompt
                    + f"\n上一次输出不可用：{exc.message}\n请只输出一个合法 JSON 对象。"
                )
                continue
            add_usage(draft_id, llm_calls=calls)
            return result
        raise OutlineError("模型没有返回可用的内容")

    def generate_outline(draft_id: str) -> None:
        draft = store.load(draft_id)
        module_count = int(draft.get("module_count") or 1)
        lessons_per_module = int(
            draft.get("lessons_per_module") or draft.get("lesson_count") or 1
        )
        parsed = generate(
            draft_id,
            OUTLINE_SYSTEM,
            render_outline_prompt(
                draft["topic"], draft["level"], module_count, lessons_per_module
            ),
            lambda raw: outline_writer.parse_outline_json(
                raw, module_count, lessons_per_module
            ),
        )
        write_outline(store, draft_id, parsed)

    def lesson_plan(draft_id: str, lesson_id: str):
        plans = outline_plans(draft_id)
        plan = next((item for item in plans if item.lesson_id == lesson_id), None)
        if plan is None:
            raise OutlineError(f"课程不存在：{lesson_id}")
        return plan

    def generate_research(draft_id: str, lesson_id: str) -> None:
        draft = store.load(draft_id)
        plan = lesson_plan(draft_id, lesson_id)
        items = concepts(draft_id)
        titles = [str(item.get("title", "")) for item in items]
        domains = [str(item.get("domain", "")) for item in items]

        def progress(done: int, total: int, hits: int) -> None:
            store.set_step(
                draft_id, "research", lesson_id=lesson_id,
                extra={"queries": done, "total": total, "hits": hits},
            )

        result = research_runner.run_research(
            plan, titles,
            budget=draft["searches_per_lesson"],
            progress=progress,
            route_for=lambda kind: route_for_query(draft, titles, domains, kind),
        )
        checks = None
        if url_checker is not None:
            # The injected checker batches URLs itself; cap the fan-out so one
            # lesson never triggers more than the check budget. Pick one hit
            # per kind first so official docs are not crowded out by one kind.
            checks = url_checker(preflight_urls(result.hits))
        research_runner.write_research(
            store, draft_id, plan, result, checks=checks
        )
        add_usage(draft_id, searches=result.searches)
        store.set_step(
            draft_id, "research", lesson_id=lesson_id,
            extra={
                "queries": result.searches,
                "hits": len(result.hits),
                "backend": result.backend,
            },
        )

    def research_payload(draft_id: str, lesson_id: str) -> str:
        path = store.path(draft_id) / f"research/{lesson_id}.json"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def research_text(draft_id: str, lesson_id: str) -> str:
        return render_research_for_prompt(research_payload(draft_id, lesson_id))

    def generate_lesson(
        draft_id: str, lesson_id: str, *, replace: bool = False
    ) -> None:
        plan = lesson_plan(draft_id, lesson_id)
        concept_ids = {item["id"] for item in concepts(draft_id)}
        usable = usable_urls_from_payload(research_payload(draft_id, lesson_id))
        output = generate(
            draft_id,
            LESSON_SYSTEM,
            render_lesson_prompt(
                render_lesson_outline(plan),
                concepts_text(draft_id, plan.concepts),
                research_text(draft_id, lesson_id),
            ),
            lambda raw: lesson_writer.parse_lesson_json(
                raw, plan, concept_ids, usable_urls=usable
            ),
        )
        lesson_writer.write_lesson(
            store, draft_id, plan, output, replace=replace, namespace=True
        )
        store.set_step(
            draft_id, "lessons", lesson_id=lesson_id,
            extra={
                "prompt_version": PROMPT_VERSION,
                "written_at": datetime.now(timezone.utc).isoformat(),
                "figure_count": len(output.figures),
            },
        )

    def evolve_draft(draft_id: str, lesson_ids: list[str]) -> dict:
        """Rewrite selected lessons of one draft and snapshot before/after.

        The batch lock is held by :class:`EvolutionJob` through
        ``run_batch_now``. A lesson that cannot be snapshotted is left
        untouched, so a rewrite never destroys the only copy of its content.
        """
        plans = {plan.lesson_id: plan for plan in outline_plans(draft_id)}
        total = len(lesson_ids)
        store.set_step(
            draft_id, "batch", status="running",
            extra={"mode": "evolve", "done": 0, "total": total},
        )
        quality_before = draft_quality(store, draft_id)
        results: list[dict] = []
        failures = 0
        for index, lesson_id in enumerate(lesson_ids, start=1):
            evolution.note_lesson(draft_id, lesson_id)
            plan = plans.get(lesson_id)
            result: dict[str, Any]
            if plan is None:
                failures += 1
                result = {
                    "lesson_id": lesson_id, "ok": False,
                    "error": "lesson not found",
                }
            else:
                result = {"lesson_id": lesson_id, "ok": False, "error": None}
                try:
                    before = snapshot_lesson(store, draft_id, plan)
                    before_path = save_snapshot(store, before)
                except Exception as exc:  # noqa: BLE001 - keep other lessons
                    failures += 1
                    result["error"] = str(exc)
                    store.set_step(
                        draft_id, "lessons", status="failed",
                        error=str(exc), lesson_id=lesson_id,
                    )
                else:
                    result["before"] = _snapshot_summary(before)
                    result["snapshot_before"] = before_path
                    store.set_step(
                        draft_id, "lessons", status="running", lesson_id=lesson_id
                    )
                    try:
                        generate_lesson(draft_id, lesson_id, replace=True)
                    except Exception as exc:  # noqa: BLE001 - keep going
                        failures += 1
                        result["error"] = str(exc)
                        store.set_step(
                            draft_id, "lessons", status="failed",
                            error=str(exc), lesson_id=lesson_id,
                        )
                    else:
                        try:
                            after = snapshot_lesson(store, draft_id, plan)
                            after_path = save_snapshot(store, after)
                        except Exception as exc:  # noqa: BLE001 - keep going
                            failures += 1
                            result["error"] = str(exc)
                            store.set_step(
                                draft_id, "lessons", status="failed",
                                error=str(exc), lesson_id=lesson_id,
                            )
                        else:
                            result.update({
                                "ok": True,
                                "after": _snapshot_summary(after),
                                "changed": compare_snapshots(before, after),
                                "snapshot_after": after_path,
                            })
                            store.set_step(
                                draft_id, "lessons", status="done",
                                lesson_id=lesson_id,
                            )
            results.append(result)
            # Count the attempt itself, including snapshot failures and
            # lessons that are missing from the outline.
            evolution.note_lesson(draft_id, lesson_id, completed=True)
            store.set_step(
                draft_id, "batch",
                extra={"mode": "evolve", "done": index, "total": total},
            )

        report = {
            "draft_id": draft_id,
            "error": None,
            "quality_before": quality_before,
            "quality_after": draft_quality(store, draft_id),
            "lessons": results,
        }
        try:
            store.write(
                draft_id,
                f"history/evolution-{timestamp_now()}.json",
                json.dumps(
                    report, ensure_ascii=False, indent=2, default=str
                ),
            )
        except OSError as exc:
            report["error"] = f"报告写入失败：{exc}"

        batch_extra = {"mode": "evolve", "done": total, "total": total}
        if failures or report["error"]:
            store.set_step(
                draft_id, "batch", status="failed",
                error=f"{failures} 课失败" if failures else report["error"],
                extra=batch_extra,
            )
        else:
            store.set_step(
                draft_id, "batch", status="done", extra=batch_extra
            )
        return report

    @router.get("/studio", response_class=HTMLResponse)
    def studio_list(request: Request):
        return templates.TemplateResponse(
            request=request, name="studio_list.html",
            context=ctx(request, drafts=store.list()),
        )

    @router.get("/studio/evolution", response_class=HTMLResponse)
    def studio_evolution(request: Request):
        groups = [
            {"draft": draft, "modules": outline_modules(draft["id"])}
            for draft in store.list()
        ]
        return templates.TemplateResponse(
            request=request, name="studio_evolution.html",
            context=ctx(request, drafts=groups),
        )

    @router.get("/api/studio/evolution/status")
    def evolution_status():
        return evolution.status()

    @router.post("/api/studio/evolution")
    def start_evolution(body: EvolutionBody):
        require_enabled()
        if not body.targets:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_request",
                    "message": "请选择至少一门课",
                },
            )

        wanted: dict[str, set[str]] = {}
        draft_order: list[str] = []
        seen: set[tuple[str, str]] = set()
        plan_cache: dict[str, list[str]] = {}

        def plan_ids(draft_id: str) -> list[str]:
            if draft_id not in plan_cache:
                plan_cache[draft_id] = [
                    plan.lesson_id for plan in outline_plans(draft_id)
                ]
            return plan_cache[draft_id]

        for target in body.targets:
            key = (target.draft_id, target.lesson_id)
            if key in seen:
                continue
            seen.add(key)
            if not ID_RE.fullmatch(target.draft_id) or not ID_RE.fullmatch(
                target.lesson_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_target",
                        "message": "草稿或课程 ID 不合法",
                    },
                )
            if not store.exists(target.draft_id):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_target",
                        "message": f"草稿不存在：{target.draft_id}",
                    },
                )
            if target.lesson_id not in plan_ids(target.draft_id):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "invalid_target",
                        "message": f"课程不存在：{target.lesson_id}",
                    },
                )
            if target.draft_id not in wanted:
                wanted[target.draft_id] = set()
                draft_order.append(target.draft_id)
            wanted[target.draft_id].add(target.lesson_id)

        groups = [
            (
                draft_id,
                [
                    lesson_id for lesson_id in plan_ids(draft_id)
                    if lesson_id in wanted[draft_id]
                ],
            )
            for draft_id in draft_order
        ]
        total = sum(len(lesson_ids) for _, lesson_ids in groups)
        try:
            evolution.start(groups, evolve_draft, inline=runner.inline)
        except EvolutionBusy:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "evolution_running",
                    "message": "演进任务进行中",
                },
            ) from None
        return {"started": total}

    @router.post("/studio")
    def studio_create(
        request: Request,
        draft_id: str = Form(...),
        topic: str = Form(...),
        level: str = Form("L2"),
        module_count: int = Form(1),
        lessons_per_module: int | None = Form(None),
        lesson_count: int | None = Form(None),
        searches_per_lesson: int = Form(20),
        search_backend: str = Form("auto"),
    ):
        if level not in LEVELS:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_level", "message": "级别必须是 L1–L4"},
            )
        try:
            store.create(
                draft_id=draft_id, topic=topic, level=level,
                module_count=module_count,
                lessons_per_module=lessons_per_module,
                lesson_count=lesson_count,
                searches_per_lesson=searches_per_lesson,
                model=config.model if config else "unconfigured",
                prompt_version=PROMPT_VERSION,
                search_backend=search_backend,
            )
        except DraftError as exc:
            raise HTTPException(
                status_code=400, detail={"code": exc.code, "message": exc.message}
            ) from None
        if config is not None and llm is not None:
            runner.start(draft_id, "outline", lambda: generate_outline(draft_id))
        return RedirectResponse(url=f"/studio/{draft_id}", status_code=303)

    @router.get("/studio/{draft_id}", response_class=HTMLResponse)
    def studio_draft(request: Request, draft_id: str):
        draft = draft_or_404(draft_id)
        outline_path = store.path(draft_id) / "outline.html"
        return templates.TemplateResponse(
            request=request, name="studio_draft.html",
            context=ctx(
                request, draft=draft,
                outline_html=(
                    outline_path.read_text(encoding="utf-8")
                    if outline_path.is_file() else ""
                ),
                modules=outline_modules(draft_id),
                lessons=[plan.lesson_id for plan in outline_plans(draft_id)],
            ),
        )

    @router.get("/studio/{draft_id}/history/{lesson_id}", response_class=HTMLResponse)
    def studio_history(request: Request, draft_id: str, lesson_id: str):
        draft = draft_or_404(draft_id)
        plan = next(
            (item for item in outline_plans(draft_id) if item.lesson_id == lesson_id),
            None,
        )
        if plan is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "lesson_not_found", "message": "课程不存在"},
            )
        current = snapshot_lesson(store, draft_id, plan)
        current_hash = (current.get("metrics") or {}).get("html_hash")
        snapshots = list_snapshots(store, draft_id, lesson_id)
        older = next(
            (
                snapshot for snapshot in snapshots
                if (snapshot.get("metrics") or {}).get("html_hash")
                != current_hash
            ),
            None,
        )
        before = older if older is not None else (
            snapshots[0] if snapshots else None
        )
        same_as_current = older is None and before is not None
        return templates.TemplateResponse(
            request=request, name="studio_history.html",
            context=ctx(
                request,
                draft=draft,
                plan=plan,
                before=before,
                current=current,
                same_as_current=same_as_current,
            ),
        )

    @router.get("/api/studio/{draft_id}")
    def studio_status(draft_id: str):
        draft = draft_or_404(draft_id)
        return {
            "id": draft["id"], "steps": draft["steps"], "usage": draft["usage"],
        }

    @router.post("/api/studio/{draft_id}/outline")
    def regenerate_outline(draft_id: str):
        draft_or_404(draft_id)
        require_enabled()
        try:
            runner.start(draft_id, "outline", lambda: generate_outline(draft_id))
        except JobBusy:
            raise HTTPException(
                status_code=409,
                detail={"code": "step_running", "message": "任务进行中"},
            ) from None
        return {"started": True}

    @router.put("/api/studio/{draft_id}/outline")
    def save_outline(draft_id: str, body: OutlineBody):
        draft = draft_or_404(draft_id)
        batch = draft["steps"].get("batch") or {}
        if batch.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "step_running",
                    "message": "批量任务进行中，暂不能保存大纲",
                },
            )
        try:
            modules = save_outline_html(store, draft_id, body.html)
        except OutlineError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_outline", "message": exc.message},
            ) from None
        lessons = [plan.lesson_id for plan in flatten_modules(modules)]
        return {
            "lessons": lessons,
            "modules": [module.module_id for module in modules],
        }

    def lesson_path(draft_id: str, lesson_id: str) -> Path:
        plan = lesson_plan(draft_id, lesson_id)
        module_id = plan.module_id or DEFAULT_MODULE_ID
        return (
            store.path(draft_id)
            / "modules" / module_id / "lessons" / f"{lesson_id}.html"
        )

    def start_lessons(draft_id: str, kind: str, body: dict | None, make_job) -> list[str]:
        draft_or_404(draft_id)
        require_enabled()
        lesson_id = (body or {}).get("lesson_id")
        if lesson_id:
            targets = [str(lesson_id)]
        else:
            targets = list(store.load(draft_id)["steps"][kind])
        try:
            for target in targets:
                runner.start(
                    draft_id, kind,
                    lambda target=target: make_job(target),
                    lesson_id=target,
                )
        except JobBusy:
            raise HTTPException(
                status_code=409,
                detail={"code": "step_running", "message": "任务进行中"},
            ) from None
        if kind == "lessons" and runner.inline:
            # Synchronous runs report a missing lesson as a request failure.
            # A lesson that failed but already existed on disk is kept, so the
            # rewrite-conflict path still returns 200 with a failed step.
            missing: list[str] = []
            for target in targets:
                try:
                    produced = lesson_path(draft_id, target).is_file()
                except OutlineError:
                    produced = False
                if not produced:
                    missing.append(target)
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "lesson_failed",
                        "message": "写课失败，未生成课程：" + "、".join(missing),
                    },
                )
        return targets

    @router.post("/api/studio/{draft_id}/research")
    def start_research(draft_id: str, body: dict | None = None):
        targets = start_lessons(
            draft_id, "research", body,
            lambda target: generate_research(draft_id, target),
        )
        return {"started": targets}

    @router.post("/api/studio/{draft_id}/lessons")
    def start_lesson_writing(draft_id: str, body: dict | None = None):
        draft_or_404(draft_id)
        payload = body or {}
        replace = bool(payload.get("replace"))
        if replace and not payload.get("lesson_id"):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_request",
                    "message": "replace 需要指定 lesson_id",
                },
            )
        targets = start_lessons(
            draft_id, "lessons", payload,
            lambda target: generate_lesson(draft_id, target, replace=replace),
        )
        return {"started": targets}

    @router.post("/api/studio/{draft_id}/batch")
    def start_batch(draft_id: str, body: dict | None = None):
        draft_or_404(draft_id)
        require_enabled()
        mode = (body or {}).get("mode")
        if mode not in {"research", "lessons"}:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_request",
                    "message": "mode 必须是 research 或 lessons",
                },
            )
        draft = store.load(draft_id)
        plans = outline_plans(draft_id)
        targets = [
            plan.lesson_id for plan in plans
            if draft["steps"][mode].get(plan.lesson_id, {}).get("status")
            in {"pending", "failed"}
        ]
        if not targets:
            if (draft["steps"].get("batch") or {}).get("status") == "running":
                raise HTTPException(
                    status_code=409,
                    detail={"code": "step_running", "message": "任务进行中"},
                )
            return {"started": []}

        def run_batch() -> None:
            failures = 0
            store.set_step(
                draft_id, "batch", status="running",
                extra={"mode": mode, "done": 0, "total": len(targets)},
            )
            for index, lesson_id in enumerate(targets, start=1):
                status = draft["steps"][mode].get(lesson_id, {}).get("status")
                replace = mode == "lessons" and status == "failed"
                store.set_step(
                    draft_id, mode, status="running", lesson_id=lesson_id
                )
                try:
                    if mode == "research":
                        generate_research(draft_id, lesson_id)
                    else:
                        generate_lesson(draft_id, lesson_id, replace=replace)
                except Exception as exc:  # noqa: BLE001 - keep going
                    failures += 1
                    store.set_step(
                        draft_id, mode, status="failed",
                        error=str(exc), lesson_id=lesson_id,
                    )
                else:
                    store.set_step(
                        draft_id, mode, status="done", lesson_id=lesson_id
                    )
                store.set_step(
                    draft_id, "batch",
                    extra={"mode": mode, "done": index, "total": len(targets)},
                )
            if failures:
                store.set_step(
                    draft_id, "batch", status="failed",
                    error=f"{failures} 课失败",
                    extra={"mode": mode, "done": len(targets),
                           "total": len(targets)},
                )
            else:
                store.set_step(
                    draft_id, "batch", status="done",
                    extra={"mode": mode, "done": len(targets),
                           "total": len(targets)},
                )

        try:
            runner.start_batch(draft_id, run_batch)
        except JobBusy:
            raise HTTPException(
                status_code=409,
                detail={"code": "step_running", "message": "任务进行中"},
            ) from None
        return {"started": targets}

    @router.post("/api/studio/{draft_id}/validate")
    def run_validation(draft_id: str, body: dict | None = None):
        draft_or_404(draft_id)
        summary = validate_draft(store, draft_id)
        quality = None
        quality_skipped = None
        quality_errors: list[str] = []
        quality_warnings: list[str] = []
        if summary.ok:
            try:
                report = quality_draft(store, draft_id)
            except QualityUnavailable:
                quality_skipped = "unavailable"
                quality_warnings = [
                    "quality.unavailable: 内容包结构无效，质量评估未运行"
                ]
            else:
                quality = report.as_dict()
                quality_errors = [
                    f"{issue.code}: {issue.message}" for issue in report.errors
                ]
                quality_warnings = [
                    f"{issue.code}: {issue.message}" for issue in report.warnings
                ]
        else:
            quality_skipped = "invalid_pack"

        verify_errors: list[str] = []
        if not (body or {}).get("skip_verify"):
            resources = _yaml(draft_id, "resources.yaml").get("resources") or []
            if resources:
                verify_errors = verify_resources(resources)

        errors = summary.errors + quality_errors + verify_errors
        warnings = summary.warnings + quality_warnings
        extra = {"issues": errors + warnings, "quality": quality}
        store.set_step(
            draft_id, "validation",
            status="done" if not errors else "failed",
            error=errors[0] if errors else None,
            extra=extra,
        )
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "quality": quality,
            "quality_skipped": quality_skipped,
        }

    @router.post("/api/studio/{draft_id}/promote")
    def run_promote(draft_id: str, body: dict | None = None):
        draft_or_404(draft_id)
        payload: dict[str, Any] = body or {}
        try:
            target = promote(
                store, draft_id, packs_root,
                force=bool(payload.get("force")),
                skip_verify=bool(payload.get("skip_verify")),
            )
        except PromoteError as exc:
            store.set_step(draft_id, "promote", status="failed", error=exc.message)
            raise HTTPException(
                status_code=400, detail={"code": exc.code, "message": exc.message}
            ) from None
        store.set_step(draft_id, "promote", status="done", extra={"path": str(target)})
        return {"path": str(target)}

    app.include_router(router)
