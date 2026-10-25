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
    "只能使用 <concepts> 中列出的概念 id，不得自造。\n"
    "要求：\n"
    "1. 中文；正文是 HTML 片段，最外层是 <article class=\"tb-lesson\">。\n"
    "2. 只用允许的标签：article/section/div/h1-h4/p/ul/ol/li/strong/em/code/pre/a/"
    "table/thead/tbody/tr/th/td/aside/figure/figcaption。禁止 script/style/事件属性。\n"
    "3. 每课至少 2 道练习；正文必须为每道练习放一个空的挂载点："
    '<div data-tb-exercise="练习id"></div>，练习 id 必须与 exercises 中的 id 完全一致。\n'
    "4. 每个概念至少被 1 道练习覆盖；每道练习的 level 不低于它覆盖的所有概念中的"
    "最高 target_level；每课至少 1 道练习达到课程 target_level。\n"
    "5. 每道练习都必须包含：id、type、concepts（概念 id 数组，至少 1 个）、"
    "level（L1–L4）、prompt、difficulty（1–5）、explanation；按题型再补充：\n"
    "   - single_choice：options=[{\"id\", \"text\"}]，answer=\"选项 id\"\n"
    "   - multi_choice：options=[...]，answer=[\"选项 id\", ...]\n"
    "   - short_answer：answer={\"accepted\": [...], \"min_hits\": 1}，"
    "rubric=[{\"dimension\", \"weight\", \"criteria\"}]（weight 合计 1.0）\n"
    "   - self_assess：rubric（weight 合计 1.0），不要 answer\n"
    "6. 每课至少 1 条 A/B 资源；资源配置：id、title、url、type、trust、license、"
    "last_verified（YYYY-MM-DD）、coverage（概念 id 数组）、why；"
    "trust 只能是 A 或 B；只引用调研资料里 authority>=2 的条目，id 形如 DOC-XXX。\n"
    "7. 只输出一个 JSON 对象，不要代码块、不要额外文字。格式：\n"
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
