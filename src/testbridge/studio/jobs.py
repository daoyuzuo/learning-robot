"""Run studio steps in background threads with persisted status.

Different lessons of one draft may run concurrently; the same step of the same
draft (or the same lesson step) is rejected while it is running.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from testbridge.studio.store import DraftStore

KINDS = ("outline", "research", "lessons", "validate", "promote")
STEP_FOR_KIND = {
    "outline": "outline", "research": "research", "lessons": "lessons",
    "validate": "validation", "promote": "promote",
}


class JobBusy(Exception):
    """A job for the same draft step is already running."""


class JobRunner:
    def __init__(self, store: DraftStore, inline: bool = False) -> None:
        self.store = store
        self.inline = inline
        self._running: set[tuple[str, str, str | None]] = set()
        self._batch_running: set[str] = set()
        self._lock = threading.Lock()

    def start(
        self,
        draft_id: str,
        kind: str,
        fn: Callable[[], None],
        *,
        lesson_id: str | None = None,
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown job kind: {kind}")
        key = (draft_id, kind, lesson_id)
        with self._lock:
            if draft_id in self._batch_running:
                raise JobBusy("batch is already running")
            if key in self._running:
                raise JobBusy(f"{kind} is already running")
            self._running.add(key)

        self.store.set_step(
            draft_id, STEP_FOR_KIND[kind], status="running", lesson_id=lesson_id
        )

        def run() -> None:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 - status carries the error
                self.store.set_step(
                    draft_id, STEP_FOR_KIND[kind], status="failed",
                    error=str(exc), lesson_id=lesson_id,
                )
            else:
                self.store.set_step(
                    draft_id, STEP_FOR_KIND[kind], status="done", lesson_id=lesson_id
                )
            finally:
                with self._lock:
                    self._running.discard(key)

        if self.inline:
            run()
        else:
            threading.Thread(target=run, daemon=True).start()

    def start_batch(self, draft_id: str, fn: Callable[[], None]) -> None:
        """Run ``fn`` as the only job of ``draft_id``.

        The callback owns per-lesson status and may mark the batch failed; the
        wrapper only fills in ``done`` when the callback left it running.
        """
        with self._lock:
            if draft_id in self._batch_running:
                raise JobBusy("batch is already running")
            if any(item[0] == draft_id for item in self._running):
                raise JobBusy("a step is already running")
            self._batch_running.add(draft_id)

        self.store.set_step(draft_id, "batch", status="running")

        def run() -> None:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 - status carries the error
                self.store.set_step(
                    draft_id, "batch", status="failed", error=str(exc)
                )
            else:
                if (
                    self.store.load(draft_id)["steps"]["batch"].get("status")
                    == "running"
                ):
                    self.store.set_step(draft_id, "batch", status="done")
            finally:
                with self._lock:
                    self._batch_running.discard(draft_id)

        if self.inline:
            run()
        else:
            threading.Thread(target=run, daemon=True).start()
