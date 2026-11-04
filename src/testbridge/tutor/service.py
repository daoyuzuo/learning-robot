"""Tutor orchestration: context, model call, parsing, storage."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from testbridge.content.repository import ContentPack
from testbridge.search import SearchError, SearchHit, SearchProvider
from testbridge.search_sources import classify_hit, trust_for_hit
from testbridge.tutor.client import LlmClient
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.context import build_context
from testbridge.tutor.parse import TutorAnswer, parse_answer
from testbridge.tutor.prompts import SYSTEM_PROMPT, render_user_prompt
from testbridge.tutor.store import TutorMessage, TutorStore

MAX_QUESTION_CHARS = 500
MAX_SELECTION_CHARS = 400
HISTORY_MESSAGES = 8
WEB_SEARCH_COUNT = 5
WEB_QUERY_CHARS = 300
WEB_CONTENT_CHARS = 1200
TRUST_ORDER = {"A": 0, "B": 1, "C": 2}


class LessonNotFoundError(Exception):
    """The requested lesson is not in the loaded pack."""


class InvalidQuestionError(Exception):
    """The question is empty or too long."""


@dataclass(frozen=True)
class TutorReply:
    answer: TutorAnswer
    saved: bool
    web_used: bool = False
    web_sources: list[dict] = field(default_factory=list)


class TutorService:
    def __init__(
        self,
        pack: ContentPack,
        store: TutorStore,
        client: LlmClient,
        config: TutorConfig,
        learner_id: str = "local",
        *,
        search: SearchProvider | None = None,
    ) -> None:
        self.pack = pack
        self.store = store
        self.client = client
        self.config = config
        self.learner_id = learner_id
        self.search = search

    @property
    def web_available(self) -> bool:
        return self.search is not None

    def history(self, lesson_id: str, limit: int = 20) -> list[TutorMessage]:
        return self.store.history(self.learner_id, lesson_id, limit)

    def _web_hits(self, context, focus: str, question: str) -> list[SearchHit]:
        if self.search is None:
            return []
        query = " ".join(
            part for part in (context.title, focus, question) if part
        ).strip()[:WEB_QUERY_CHARS]
        if not query:
            return []
        try:
            hits = self.search.search(query, count=WEB_SEARCH_COUNT)
        except SearchError:
            return []
        ranked: list[tuple[int, int, SearchHit]] = []
        seen: set[str] = set()
        for index, hit in enumerate(hits):
            if not hit.url or hit.url in seen:
                continue
            seen.add(hit.url)
            trust = trust_for_hit(hit)
            if trust == "D":
                continue
            ranked.append((TRUST_ORDER.get(trust, 3), index, SearchHit(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet[:400],
                summary=hit.summary[:400],
                content=hit.content[:WEB_CONTENT_CHARS],
                authority=hit.authority,
                date=hit.date,
                is_oa=hit.is_oa,
                oa_url=hit.oa_url,
                work_type=hit.work_type,
            )))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [hit for _, _, hit in ranked[:WEB_SEARCH_COUNT]]

    def ask(
        self,
        lesson_id: str,
        anchor: str,
        question: str,
        *,
        use_web: bool = True,
        selection: str = "",
    ) -> TutorReply:
        if lesson_id not in self.pack.lessons:
            raise LessonNotFoundError(lesson_id)

        text = question.strip()
        if not text or len(text) > MAX_QUESTION_CHARS:
            raise InvalidQuestionError("question must be 1-500 characters")

        # A selection is whatever the learner happened to highlight, so it is
        # trimmed instead of rejected: refusing to answer because they dragged
        # too far would be a worse experience than quoting the first 400 chars.
        quoted = " ".join((selection or "").split())[:MAX_SELECTION_CHARS]

        context = build_context(self.pack, lesson_id)
        focus = anchor if anchor in context.headings else ""
        history = [
            (message.role, message.content)
            for message in self.store.history(
                self.learner_id, lesson_id, HISTORY_MESSAGES
            )
        ]

        web_hits = self._web_hits(context, focus, text) if use_web else []
        raw = self.client.complete(
            SYSTEM_PROMPT,
            render_user_prompt(
                context, focus, text, history,
                web_hits=web_hits, today=date.today().isoformat(),
                selection=quoted,
            ),
        )
        answer = parse_answer(
            raw,
            headings=context.headings,
            resource_ids=context.resource_ids,
            web_urls=[hit.url for hit in web_hits],
        )

        saved = True
        try:
            self.store.append(
                learner_id=self.learner_id,
                lesson_id=lesson_id,
                anchor=focus,
                role="user",
                content=text,
                selection=quoted,
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
                selection=quoted,
            )
        except sqlite3.Error:
            saved = False

        web_sources = [
            {
                "url": hit.url,
                "title": hit.title,
                "trust": trust_for_hit(hit),
                "kind": classify_hit(hit),
            }
            for hit in web_hits
        ]
        return TutorReply(
            answer=answer, saved=saved, web_used=bool(web_hits),
            web_sources=web_sources,
        )
