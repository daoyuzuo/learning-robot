"""Minimal OpenAI-compatible chat client."""

from __future__ import annotations

import time
from typing import Protocol

import httpx

from testbridge.tutor.config import TutorConfig

TRANSIENT_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
RETRY_TIMEOUT_FACTOR = 3.0
MAX_RETRY_TIMEOUT = 300.0


class TutorUpstreamError(Exception):
    """The provider answered with an error or an unusable body."""


class TutorTimeoutError(Exception):
    """The provider did not answer within the configured timeout."""


class LlmClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class OpenAICompatibleClient:
    def __init__(
        self,
        config: TutorConfig,
        transport: httpx.BaseTransport | None = None,
        *,
        retry_delay: float = 1.0,
        attempts: int = 2,
    ) -> None:
        self.config = config
        self.retry_delay = retry_delay
        self.attempts = max(1, attempts)
        self._client = httpx.Client(
            timeout=config.timeout,
            transport=transport,
        )

    def _attempt_timeout(self, attempt: int) -> float:
        if attempt == 0:
            return self.config.timeout
        return min(
            self.config.timeout * RETRY_TIMEOUT_FACTOR ** attempt,
            MAX_RETRY_TIMEOUT,
        )

    def _wait(self) -> None:
        if self.retry_delay > 0:
            time.sleep(self.retry_delay)

    def complete(self, system: str, user: str) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        last = self.attempts - 1
        for attempt in range(self.attempts):
            try:
                response = self._client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    json=payload,
                    timeout=self._attempt_timeout(attempt),
                )
            except httpx.TimeoutException as exc:
                if attempt == last:
                    raise TutorTimeoutError("upstream timed out") from exc
                self._wait()
                continue
            except httpx.HTTPError as exc:
                if attempt == last:
                    raise TutorUpstreamError("upstream request failed") from exc
                self._wait()
                continue

            if response.status_code in TRANSIENT_STATUS and attempt < last:
                self._wait()
                continue
            if response.status_code >= 400:
                raise TutorUpstreamError(
                    f"upstream status {response.status_code}"
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise TutorUpstreamError("upstream returned non-JSON") from exc

            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices:
                raise TutorUpstreamError("upstream returned no choices")
            message = (
                choices[0].get("message")
                if isinstance(choices[0], dict)
                else None
            )
            content = (
                message.get("content") if isinstance(message, dict) else None
            )
            if not isinstance(content, str) or not content.strip():
                raise TutorUpstreamError("upstream returned empty content")
            return content
        raise TutorUpstreamError("upstream request failed")

    def close(self) -> None:
        self._client.close()
