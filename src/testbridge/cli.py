"""Command-line interface for TestBridge."""

from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from testbridge.build import build_pack
from testbridge.content.repository import list_packs, load_pack
from testbridge.contract.validator import validate_pack
from testbridge.evidence.store import EvidenceStore
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import Goal, LearningStore
from testbridge.tutor.client import (
    LlmClient,
    OpenAICompatibleClient,
    TutorTimeoutError,
    TutorUpstreamError,
)
from testbridge.tutor.config import TutorConfig, load_config, missing_vars
from testbridge.tutor.env_store import (
    EnvWriteError,
    display_url,
    export_lines,
    secret_status,
    write_user_env,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


def _load_app(pack_dir: Path, db_path: Path) -> FastAPI:
    """Load the repo-local web app without requiring a wheel-packaged ``web``."""
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from web.app import create_app

    return create_app(
        pack_dir, db_path,
        studio_llm=None, studio_search=None, studio_inline=False,
    )


def build_tutor_client(config: TutorConfig) -> LlmClient:
    return OpenAICompatibleClient(config)


def _load_learning(pack_path: str, db_path: str, learner_id: str = "local") -> LearningService:
    pack = load_pack(Path(pack_path))
    return LearningService(
        pack, EvidenceStore(Path(db_path)), LearningStore(Path(db_path)), learner_id
    )


def _run_quality(
    pack_dir: Path,
    research_dir: str | None,
    budget: int | None,
    as_json: bool,
) -> int:
    from testbridge.quality.evaluate import QualityUnavailable, evaluate_pack

    explicit_research = research_dir is not None
    research_path = Path(research_dir) if research_dir else None

    draft_path = pack_dir / "draft.json"
    if draft_path.is_file():
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            draft = {}
        if research_path is None:
            research_path = pack_dir / "research"
        if budget is None and isinstance(draft.get("searches_per_lesson"), int):
            budget = draft["searches_per_lesson"]

    if budget is not None and budget < 1:
        print(f"ERROR budget: must be >= 1: {budget}")
        return 2

    if explicit_research and (research_path is None or not research_path.is_dir()):
        print(f"ERROR research_dir: not found: {research_path}")
        return 2

    try:
        report = evaluate_pack(
            pack_dir, research_dir=research_path, budget=budget
        )
    except QualityUnavailable as exc:
        for issue in exc.report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        for issue in exc.report.warnings:
            print(f"WARN {issue.code}: {issue.message}")
        print("run tb validate first")
        return 2

    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"quality: {report.score}/100")
        for issue in report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        for issue in report.warnings:
            print(f"WARN {issue.code}: {issue.message}")
        print(
            "provenance: "
            + ("evaluated" if report.provenance_evaluated else "not evaluated")
        )
        print(
            "research: "
            + ("evaluated" if report.research_evaluated else "not evaluated")
        )
    return 0 if report.ok else 1


REQUIRED_LLM_VARS = (
    "TESTBRIDGE_LLM_BASE_URL",
    "TESTBRIDGE_LLM_API_KEY",
    "TESTBRIDGE_LLM_MODEL",
)


def _valid_base_url(value: str) -> bool:
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and bool(parts.hostname)


def _prompt_value(label: str, current: str, *, secret: bool = False) -> str:
    shown = secret_status(current) if secret else current
    suffix = f" [{shown}]" if current else ""
    prompt = f"{label}{suffix}: "
    value = getpass.getpass(prompt) if secret else input(prompt)
    return value.strip() or current


def _cmd_env_init(args) -> int:
    current = {name: os.environ.get(name, "") for name in REQUIRED_LLM_VARS}
    base_url = args.base_url or _prompt_value(
        "TESTBRIDGE_LLM_BASE_URL", current["TESTBRIDGE_LLM_BASE_URL"]
    )
    model = args.model or _prompt_value(
        "TESTBRIDGE_LLM_MODEL", current["TESTBRIDGE_LLM_MODEL"]
    )
    timeout = args.timeout or _prompt_value(
        "TESTBRIDGE_LLM_TIMEOUT", os.environ.get("TESTBRIDGE_LLM_TIMEOUT", "")
    ) or "90"
    api_key = _prompt_value(
        "TESTBRIDGE_LLM_API_KEY", current["TESTBRIDGE_LLM_API_KEY"], secret=True
    )

    if not _valid_base_url(base_url):
        print(
            "ERROR env: base URL must start with http:// or https://",
            file=sys.stderr,
        )
        return 2
    if not model:
        print("ERROR env: model must not be empty", file=sys.stderr)
        return 2
    try:
        timeout_value = float(timeout)
    except ValueError:
        timeout_value = 0
    if timeout_value <= 0:
        print("ERROR env: timeout must be > 0", file=sys.stderr)
        return 2
    if not api_key:
        print("ERROR env: API key must not be empty", file=sys.stderr)
        return 2

    values = {
        "TESTBRIDGE_LLM_BASE_URL": base_url,
        "TESTBRIDGE_LLM_API_KEY": api_key,
        "TESTBRIDGE_LLM_MODEL": model,
        "TESTBRIDGE_LLM_TIMEOUT": timeout,
    }
    print("will set:")
    for name, value in values.items():
        shown = secret_status(value) if name == "TESTBRIDGE_LLM_API_KEY" else value
        print(f"  {name} = {shown}")

    if args.dry_run:
        return 0
    answer = input("write these to your user environment? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        print("cancelled")
        return 1
    if os.name != "nt":
        print("add these lines to your shell profile, then restart the shell:")
        for line in export_lines(values):
            print(line)
        return 0
    try:
        write_user_env(values)
    except EnvWriteError as exc:
        print(f"ERROR env: could not write user environment: {exc}", file=sys.stderr)
        return 2
    print("saved. reopen your terminal and restart any running Web service.")
    return 0


def _cmd_doctor(args) -> int:
    required = [
        ("llm.base_url", "TESTBRIDGE_LLM_BASE_URL", display_url),
        ("llm.model", "TESTBRIDGE_LLM_MODEL", str),
        ("llm.api_key", "TESTBRIDGE_LLM_API_KEY", secret_status),
    ]
    missing = []
    for label, name, formatter in required:
        value = os.environ.get(name, "")
        if not value:
            missing.append(name)
            print(f"{label:16} missing  {name}")
            continue
        print(f"{label:16} set      {formatter(value)}")

    timeout = os.environ.get("TESTBRIDGE_LLM_TIMEOUT") or "30"
    timeout_state = "set" if os.environ.get("TESTBRIDGE_LLM_TIMEOUT") else "default"
    print(f"{'llm.timeout':16} {timeout_state:8} {timeout}s")

    mailto = os.environ.get("TESTBRIDGE_OPENALEX_MAILTO")
    print(f"{'openalex.mailto':16} {'set' if mailto else 'unset'}")
    for name, default in (
        ("TESTBRIDGE_OPENALEX_BASE_URL", "https://api.openalex.org"),
        ("TESTBRIDGE_OPENALEX_TIMEOUT", "10"),
    ):
        value = os.environ.get(name)
        state = "set" if value else "default"
        print(f"{name.lower():16} {state:8} {value or default}")

    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 2
    if not args.probe:
        return 0

    config = load_config()
    if config is None:
        print("ERROR doctor: missing environment variables", file=sys.stderr)
        return 2
    client = build_tutor_client(config)
    started = time.perf_counter()
    try:
        reply = client.complete("你是连通性测试，请只回复 ok。", "ok")
    except TutorTimeoutError:
        print("ERROR doctor: upstream timed out", file=sys.stderr)
        return 2
    except TutorUpstreamError as exc:
        print(f"ERROR doctor: {exc}", file=sys.stderr)
        return 2
    elapsed = (time.perf_counter() - started) * 1000
    print(f"latency: {elapsed:.0f} ms")
    print(f"reply: {reply.strip()[:40]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tb")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a content pack")
    validate.add_argument("pack")

    quality = sub.add_parser("quality", help="check content quality")
    quality.add_argument("pack")
    quality.add_argument("--research-dir", default=None)
    quality.add_argument("--budget", type=int, default=None)
    quality.add_argument("--json", action="store_true")

    build = sub.add_parser("build", help="build standalone lessons")
    build.add_argument("pack")
    build.add_argument("--out", default="dist")
    build.add_argument("--lesson", default=None)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("pack")
    serve.add_argument("--db", default="data/testbridge.db")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    listing = sub.add_parser("list", help="list packs under a root")
    listing.add_argument("root", default="content-packs", nargs="?")

    export = sub.add_parser("evidence-export")
    export.add_argument("db")
    export.add_argument("out")

    import_cmd = sub.add_parser("evidence-import")
    import_cmd.add_argument("db")
    import_cmd.add_argument("path")

    rebuild = sub.add_parser("rebuild-state")
    rebuild.add_argument("--pack", default="content-packs/sample-sensors")
    rebuild.add_argument("--db", default="data/testbridge.db")
    rebuild.add_argument("--learner-id", default="local")

    goal = sub.add_parser("goal")
    goal_sub = goal.add_subparsers(dest="goal_command", required=True)
    goal_show = goal_sub.add_parser("show")
    goal_show.add_argument("--db", default="data/testbridge.db")
    goal_show.add_argument("--learner-id", default="local")
    goal_set = goal_sub.add_parser("set")
    goal_set.add_argument("--db", default="data/testbridge.db")
    goal_set.add_argument("--learner-id", default="local")
    goal_set.add_argument("--target-role", default=None)
    goal_set.add_argument("--weekly-hours", type=float, default=None)
    goal_set.add_argument("--daily-minutes", type=int, default=None)
    goal_set.add_argument("--override", action="append", default=None)

    readiness = sub.add_parser("readiness")
    readiness.add_argument("--pack", default="content-packs/sample-sensors")
    readiness.add_argument("--db", default="data/testbridge.db")
    readiness.add_argument("--learner-id", default="local")

    today = sub.add_parser("today")
    today.add_argument("--pack", default="content-packs/sample-sensors")
    today.add_argument("--db", default="data/testbridge.db")
    today.add_argument("--learner-id", default="local")

    tutor = sub.add_parser("tutor", help="AI tutor utilities")
    tutor_sub = tutor.add_subparsers(dest="tutor_command", required=True)
    tutor_sub.add_parser("check", help="verify the configured LLM endpoint")

    env = sub.add_parser("env", help="manage user-level configuration")
    env_sub = env.add_subparsers(dest="env_command", required=True)
    env_init = env_sub.add_parser("init", help="write TESTBRIDGE_LLM_* once")
    env_init.add_argument("--base-url", default=None)
    env_init.add_argument("--model", default=None)
    env_init.add_argument("--timeout", default=None)
    env_init.add_argument("--dry-run", action="store_true")

    doctor = sub.add_parser("doctor", help="check local configuration")
    doctor.add_argument("--probe", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _cmd_doctor(args)

    if args.command == "env":
        if args.env_command == "init":
            return _cmd_env_init(args)

    if args.command == "validate":
        report = validate_pack(Path(args.pack))
        for issue in report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        for issue in report.warnings:
            print(f"WARN {issue.code}: {issue.message}")
        print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 0 if report.ok else 1

    if args.command == "quality":
        return _run_quality(
            Path(args.pack), args.research_dir, args.budget, args.json
        )

    if args.command == "build":
        paths = build_pack(Path(args.pack), Path(args.out), args.lesson)
        for path in paths:
            print(path)
        return 0

    if args.command == "serve":
        import uvicorn

        app = _load_app(Path(args.pack), Path(args.db))
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.command == "list":
        for info in list_packs(Path(args.root)):
            print(f"{info.meta.id}\t{info.meta.version}\t{info.path}")
        return 0

    if args.command == "evidence-export":
        count = EvidenceStore(Path(args.db)).export_jsonl(Path(args.out))
        print(f"exported {count}")
        return 0

    if args.command == "evidence-import":
        count = EvidenceStore(Path(args.db)).import_jsonl(
            Path(args.path),
            on_warning=lambda message: print(f"WARN {message}", file=sys.stderr),
        )
        print(f"imported {count}")
        return 0

    if args.command == "rebuild-state":
        service = _load_learning(args.pack, args.db, args.learner_id)
        result = rebuild_state(service)
        print(
            f"rebuilt {result.events} events, {result.concepts} concepts, "
            f"{result.reviews} reviews"
        )
        if result.skipped_concepts:
            print(
                f"WARN skipped concepts: {', '.join(result.skipped_concepts)}",
                file=sys.stderr,
            )
        if result.skipped_exercises:
            print(
                f"WARN skipped exercises: {', '.join(result.skipped_exercises)}",
                file=sys.stderr,
            )
        for message in result.warnings:
            print(f"WARN {message}", file=sys.stderr)
        return 0

    if args.command == "goal":
        if args.goal_command == "show":
            goal = LearningStore(Path(args.db)).get_goal(args.learner_id)
            print(goal)
            return 0
        store = LearningStore(Path(args.db))
        existing = store.get_goal(args.learner_id)
        try:
            overrides = dict(existing.concept_overrides)
            for item in args.override or []:
                key, sep, value = item.partition("=")
                if not sep or not key:
                    raise ValueError(f"invalid override {item!r}")
                multiplier = float(value)
                if not math.isfinite(multiplier) or multiplier < 0:
                    raise ValueError(f"invalid override {item!r}")
                overrides[key] = multiplier
            target_role = (
                args.target_role if args.target_role is not None else existing.target_role
            )
            weekly_hours = (
                args.weekly_hours if args.weekly_hours is not None else existing.weekly_hours
            )
            daily_minutes = (
                args.daily_minutes if args.daily_minutes is not None else existing.daily_minutes
            )
            if daily_minutes <= 0:
                raise ValueError("daily minutes must be > 0")
            if not math.isfinite(weekly_hours):
                raise ValueError("weekly hours must be finite")
            if weekly_hours < 0:
                raise ValueError("weekly hours must be >= 0")
        except ValueError as exc:
            print(f"ERROR goal: {exc}", file=sys.stderr)
            return 2
        store.set_goal(Goal(
            learner_id=args.learner_id, target_role=target_role,
            weekly_hours=weekly_hours, daily_minutes=daily_minutes,
            concept_overrides=overrides,
        ))
        print("goal updated")
        return 0

    if args.command == "readiness":
        service = _load_learning(args.pack, args.db, args.learner_id)
        view = service.readiness()
        print(f"readiness: {view.total:.2f}")
        for module_id, value in view.by_module.items():
            print(f"  {module_id}: {value:.2f}")
        for reason in view.gate_reasons:
            print(f"  gate: {reason}")
        return 0

    if args.command == "today":
        service = _load_learning(args.pack, args.db, args.learner_id)
        plan = service.today_plan()
        print(f"today: {len(plan.items)} items, {plan.total_minutes}/{plan.budget_minutes} minutes")
        for item in plan.items:
            print(f"  {item.type}: {item.reason} ({item.estimated_minutes}m)")
        if plan.empty:
            print(f"  {plan.suggestion or 'no mandatory work'}")
        return 0

    if args.command == "tutor":
        config = load_config()
        if config is None:
            print(
                "ERROR tutor: missing environment variables: "
                + ", ".join(missing_vars()),
                file=sys.stderr,
            )
            return 2
        client = build_tutor_client(config)
        started = time.perf_counter()
        try:
            reply = client.complete("你是连通性测试，请只回复 ok。", "ok")
        except TutorTimeoutError:
            print("ERROR tutor: upstream timed out", file=sys.stderr)
            return 2
        except TutorUpstreamError as exc:
            print(f"ERROR tutor: {exc}", file=sys.stderr)
            return 2
        elapsed = (time.perf_counter() - started) * 1000
        print(f"model: {config.model}")
        print(f"latency: {elapsed:.0f} ms")
        print(f"reply: {reply.strip()[:40]}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
