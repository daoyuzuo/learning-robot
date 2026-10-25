"""Prompts for outline and lesson generation.

Model output is untrusted: callers must parse and sanitize it before writing.
"""

from __future__ import annotations

OUTLINE_SYSTEM = (
    "你是 TestBridge 的课程设计师。为给定主题设计一个模块。\n"
    "要求：\n"
    "1. 概念 2–6 个，id 用小写 kebab-case 英文；先修关系无环。\n"
    "2. 课程节数与用户要求一致，id 形如 L-XXX-001。\n"
    "3. 每节课给出 1–5 条 objectives、1–3 条 exercise_intents、1–3 条 research_queries。\n"
    "4. 只输出一个 JSON 对象，不要代码块、不要额外文字。格式：\n"
    '{"module_title": "...", "concepts": [{"id", "title", "domain", '
    '"target_level", "prerequisites", "weight", "evidence_criteria": '
    '[{"id", "description", "level"}]}], "lessons": [{"id", "title", '
    '"minutes", "objectives", "exercise_intents", "research_queries"}]}'
)

LESSON_SYSTEM = (
    "你是 TestBridge 的课程作者。根据大纲、概念表和调研资料写一节课。\n"
    "要求：\n"
    "1. 中文；正文是 HTML 片段，最外层是 <article class=\"tb-lesson\">。\n"
    "2. 只用允许的标签：article/section/h1-h4/p/ul/ol/li/strong/em/code/pre/"
    "table/thead/tbody/tr/th/td/aside/figure/figcaption。禁止 script/style/事件属性。\n"
    "3. 每节课 2–3 道练习；题型限 single_choice / multi_choice / short_answer / self_assess。\n"
    "4. 资源只引用调研资料里 authority>=2 的条目，id 形如 DOC-XXX。\n"
    "5. 只输出一个 JSON 对象，不要代码块、不要额外文字。格式：\n"
    '{"manifest": {"title", "minutes", "objectives"}, "html": "...", '
    '"exercises": [...], "resources": [...]}'
)


def render_outline_prompt(topic: str, level: str, lesson_count: int) -> str:
    return (
        f"主题：{topic}\n目标级别：{level}\n课程节数：{lesson_count}\n"
        "请输出模块大纲 JSON。"
    )


def render_lesson_prompt(
    lesson_html: str, concepts_text: str, research_text: str
) -> str:
    return (
        f"<outline>\n{lesson_html}\n</outline>\n"
        f"<concepts>\n{concepts_text}\n</concepts>\n"
        f"<research>\n{research_text}\n</research>\n"
        "请输出这一节课的 JSON。"
    )
