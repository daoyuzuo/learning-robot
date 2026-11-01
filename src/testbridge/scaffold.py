"""Create a minimal, valid ``tb/1`` course pack skeleton.

This is deterministic scaffolding, not generation: the authoring AI replaces
the placeholder concept, lesson, exercise and resource. The skeleton exists so
that ``tb validate`` passes immediately and the file contract is visible.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
LEVELS = {"L1", "L2", "L3", "L4"}
PACK_ID = "core"
LESSON_ID = "L-001-001"


class ScaffoldError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def scaffold_pack(
    root: Path,
    pack_id: str,
    title: str,
    *,
    description: str = "",
    level: str = "L2",
) -> Path:
    """Write a valid placeholder pack under ``root/pack_id``.

    Existing directories and invalid IDs are rejected before anything is
    written. The caller owns choosing the root (usually ``content-packs``).
    """
    if not ID_RE.fullmatch(pack_id):
        raise ScaffoldError(
            "invalid_id", "课程包 ID 只能包含字母、数字和连字符，且以字母开头"
        )
    if level not in LEVELS:
        raise ScaffoldError("invalid_level", "级别必须是 L1–L4")
    title = title.strip()
    if not title:
        raise ScaffoldError("invalid_title", "课程标题不能为空")
    target = root / pack_id
    if target.exists():
        raise ScaffoldError("pack_exists", f"目标目录已存在：{target}")
    today = datetime.now(timezone.utc).date().isoformat()
    module_dir = target / "modules" / "M01"
    lesson_dir = module_dir / "lessons"
    lesson_dir.mkdir(parents=True)

    _dump(target / "pack.yaml", {
        "schema": "tb/1",
        "id": pack_id,
        "version": "0.1.0",
        "title": title,
        "description": description.strip() or title,
        "language": "zh-CN",
        "license": "CC-BY-4.0",
        "authors": ["author"],
        "created": today,
        "fixture": False,
    })
    _dump(target / "concepts.yaml", {
        "schema": "tb/1",
        "concepts": [{
            "id": PACK_ID,
            "title": "待填概念",
            "domain": "待填领域",
            "target_level": level,
            "prerequisites": [],
            "weight": 1.0,
            "evidence_criteria": [{
                "id": "ev-core",
                "description": "能解释并应用待填概念",
                "level": level,
            }],
        }],
    })
    _dump(target / "exercises.yaml", {
        "schema": "tb/1",
        "exercises": [
            {
                "id": "EX-1",
                "type": "single_choice",
                "concepts": [PACK_ID],
                "level": level,
                "prompt": "待填题目：请替换成能检验本课目标的问题",
                "options": [
                    {"id": "a", "text": "选项 A"},
                    {"id": "b", "text": "选项 B"},
                ],
                "answer": "a",
                "explanation": "待填解析",
                "difficulty": 1,
            },
            {
                "id": "EX-2",
                "type": "short_answer",
                "concepts": [PACK_ID],
                "level": level,
                "prompt": "待填简答题：请换成需要解释或设计的开放题",
                "answer": {
                    "accepted": ["待填关键词一", "待填关键词二"],
                    "min_hits": 1,
                },
                "rubric": [
                    {"dimension": "结论", "weight": 0.5, "criteria": "给出可判定结论"},
                    {"dimension": "依据", "weight": 0.5, "criteria": "给出依据或步骤"},
                ],
                "explanation": "待填解析",
                "difficulty": 2,
            },
        ],
    })
    _dump(target / "resources.yaml", {
        "schema": "tb/1",
        "resources": [{
            "id": "DOC-1",
            "title": "待替换为官方/权威资料",
            "url": "https://example.com/",
            "type": "official-doc",
            "kind": "official_docs",
            "role": "required",
            "trust": "B",
            "license": "待填",
            "last_verified": today,
            "coverage": [PACK_ID],
            "why": "待填：工程上什么时候用这份资料",
        }],
    })
    _dump(module_dir / "module.yaml", {
        "schema": "tb/1",
        "id": "M01",
        "title": "待填模块",
        "priority": "P1",
        "concepts": [PACK_ID],
        "lessons": [LESSON_ID],
        "order": 1,
    })
    manifest = {
        "schema": "tb/1",
        "id": LESSON_ID,
        "title": "待填课程",
        "module": "M01",
        "concepts": [PACK_ID],
        "target_level": level,
        "minutes": 30,
        "objectives": ["待填：学完能做什么"],
        "prerequisites": [],
        "exercises": ["EX-1", "EX-2"],
        "resources": ["DOC-1"],
    }
    lesson_html = (
        '<script type="application/json" id="tb-manifest">\n'
        f"{json.dumps(manifest, ensure_ascii=False, indent=2)}\n"
        "</script>\n"
        '<article class="tb-lesson">\n'
        "  <h1>待填课程</h1>\n"
        "  <p>待填正文：把这一课讲清楚，并在每道练习的位置放一个空挂载点。</p>\n"
        '  <div data-tb-exercise="EX-1"></div>\n'
        '  <div data-tb-exercise="EX-2"></div>\n'
        "</article>\n"
    )
    (lesson_dir / f"{LESSON_ID}.html").write_text(lesson_html, encoding="utf-8")
    return target
