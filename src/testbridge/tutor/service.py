"""Tutor orchestration: context, model call, parsing, storage."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from testbridge.content.repository import ContentPack
from testbridge.tutor.client import LlmClient
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.context import build_context
from testbridge.tutor.parse import TutorAnswer, parse_answer
from testbridge.tutor.prompts import SYSTEM_PROMPT, render_user_prompt
from testbridge.tutor.store import TutorMessage, TutorStore

MAX_QUESTION_CHARS = 500
HISTORY_MESSAGES = 8


class LessonNotFoundError(Exception):
    """The requested lesson is not in the loaded pack."""


class InvalidQuestionError(Exception):
    """The question is empty or too long."""


@dataclass(frozen=True)
class TutorReply:
    answer: TutorAnswer
    saved: bool


class TutorService:
    def __init__(
        self,
        pack: ContentPack,
        store: TutorStore,
        client: LlmClient,
        config: TutorConfig,
        learner_id: str = "local",
    ) -> None:
        self.pack = pack
        self.store = store
        self.client = client
        self.config = config
        self.learner_id = learner_id

    def history(self, lesson_id: str, limit: int = 20) -> list[TutorMessage]:
        return self.store.history(self.learner_id, lesson_id, limit)

    def ask(self, lesson_id: str, anchor: str, question: str) -> TutorReply:
        if lesson_id not in self.pack.lessons:
            raise LessonNotFoundError(lesson_id)

        text = question.strip()
        if not text or len(text) > MAX_QUESTION_CHARS:
            raise InvalidQuestionError("question must be 1-500 characters")

        context = build_context(self.pack, lesson_id)
        focus = anchor if anchor in context.headings else ""
        history = [
            (message.role, message.content)
            for message in self.store.history(
                self.learner_id, lesson_id, HISTORY_MESSAGES
            )
        ]

        raw = self.client.complete(
            SYSTEM_PROMPT,
            render_user_prompt(context, focus, text, history),
        )
        answer = parse_answer(
            raw, headings=context.headings, resource_ids=context.resource_ids
        )

        saved = True
        try:
            self.store.append(
                learner_id=self.learner_id,
                lesson_id=lesson_id,
                anchor=focus,
                role="user",
                content=text,
            )
            self.store.append(
                learner_id=self.learner_id,
                lesson_id=lesson_id,
                anchor=focus,
                role="assistant",
                content=answer.answer,
                basis=answer.basis,
                citations=answer.citations,
                model=self.config.model,
            )
        except sqlite3.Error:
            saved = False

        return TutorReply(answer=answer, saved=saved)
