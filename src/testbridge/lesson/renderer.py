"""Render a validated lesson into a shell-ready view."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from testbridge.content.repository import ContentPack, Lesson
from testbridge.contract.models import Concept, Exercise, Module, Resource, Widget
from testbridge.contract.sanitize import sanitize_fragment


@dataclass(frozen=True)
class WidgetView:
    widget: Widget
    template_html: str


@dataclass(frozen=True)
class LessonView:
    lesson: Lesson
    module: Module
    concepts: list[Concept]
    exercises: list[Exercise]
    resources: list[Resource]
    widgets: list[WidgetView]
    body_html: str
    prev_lesson: Lesson | None
    next_lesson: Lesson | None


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_exercise_form(exercise: Exercise) -> str:
    if exercise.type == "single_choice":
        fields = "".join(
            f'<label><input type="radio" name="answer" value="{_esc(option.id)}"> {_esc(option.text)}</label>'
            for option in exercise.options
        )
    elif exercise.type == "multi_choice":
        fields = "".join(
            f'<label><input type="checkbox" name="answer" value="{_esc(option.id)}"> {_esc(option.text)}</label>'
            for option in exercise.options
        )
    elif exercise.type == "short_answer":
        fields = '<textarea name="answer" rows="4" placeholder="用自己的话回答"></textarea>'
    elif exercise.type == "self_assess":
        fields = "".join(
            f'<label><input type="checkbox" name="checked" value="{_esc(item.dimension)}"> '
            f"{_esc(item.dimension)}：{_esc(item.criteria)}</label>"
            for item in exercise.rubric
        )
    else:
        fields = (
            '<input type="text" name="path" placeholder="附件路径，例如 data/artifacts/run.log">'
            '<textarea name="notes" rows="3" placeholder="观察与结论"></textarea>'
            '<div class="tb-self-check">'
            + "".join(
                f'<label><input type="checkbox" name="checked" value="{_esc(item.dimension)}"> '
                f"{_esc(item.dimension)}：{_esc(item.criteria)}</label>"
                for item in exercise.rubric
            )
            + "</div>"
        )

    hints = "".join(
        f'<p class="tb-hint" data-level="{hint.level}" hidden>{_esc(hint.text)}</p>'
        for hint in exercise.hints
    )
    return f"""<form class="tb-exercise" data-exercise-id="{_esc(exercise.id)}" data-exercise-type="{exercise.type}">
  <p class="tb-prompt">{_esc(exercise.prompt)}</p>
  <div class="tb-fields">{fields}</div>
  <div class="tb-actions"><button type="submit">提交</button><button type="button" class="tb-hint-button">提示</button></div>
  <div class="tb-hints">{hints}</div>
  <div class="tb-feedback" hidden></div>
</form>"""


def render_widget(widget: Widget, template_html: str) -> str:
    controls = "".join(
        f'<label>{_esc(parameter.label)} '
        f'<input type="range" data-param="{_esc(parameter.id)}" '
        f'min="{parameter.min}" max="{parameter.max}" value="{parameter.default}" step="any">'
        f"<output>{parameter.default}</output></label>"
        for parameter in widget.spec.parameters
    )
    rendered = template_html
    for parameter in widget.spec.parameters:
        rendered = rendered.replace("{{" + parameter.id + "}}", str(parameter.default))
    return f"""<figure class="tb-widget" data-widget-id="{_esc(widget.id)}">
  <div class="tb-widget-controls">{controls}</div>
  <div class="tb-widget-canvas">{rendered}</div>
  <template class="tb-widget-template">{template_html}</template>
  <figcaption>{_esc(widget.caption)}</figcaption>
</figure>"""


def render_lesson(pack: ContentPack, lesson_id: str) -> LessonView:
    lesson = pack.lesson(lesson_id)
    manifest = lesson.manifest
    body = sanitize_fragment(lesson.body_html)
    exercises = [pack.exercise(item) for item in manifest.exercises]
    resources = [pack.resource(item) for item in manifest.resources]
    concepts = [pack.concept(item) for item in manifest.concepts]

    widget_ids = list(dict.fromkeys(re.findall(r'data-tb-widget="([^"]+)"', body)))
    widgets: list[WidgetView] = []
    for widget_id in widget_ids:
        widget = pack.widget(widget_id)
        template_path = pack.root / widget.spec.template
        widgets.append(
            WidgetView(widget=widget, template_html=template_path.read_text(encoding="utf-8"))
        )

    for exercise in exercises:
        pattern = re.compile(
            rf'<div\b[^>]*data-tb-exercise="{re.escape(exercise.id)}"[^>]*>\s*</div>',
            re.IGNORECASE,
        )
        body = pattern.sub(render_exercise_form(exercise), body)

    for view in widgets:
        pattern = re.compile(
            rf'<div\b[^>]*data-tb-widget="{re.escape(view.widget.id)}"[^>]*>\s*</div>',
            re.IGNORECASE,
        )
        body = pattern.sub(render_widget(view.widget, view.template_html), body)

    prev_lesson, next_lesson = pack.prev_next(lesson_id)
    return LessonView(
        lesson=lesson,
        module=pack.modules[manifest.module],
        concepts=concepts,
        exercises=exercises,
        resources=resources,
        widgets=widgets,
        body_html=body,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
    )
