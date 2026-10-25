"""Minimal OpenAI-compatible chat client."""

from __future__ import annotations

from typing import Protocol

import httpx

from testbridge.tutor.config import TutorConfig


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
    ) -> None:
        self.config = config
        self._client = httpx.Client(
            timeout=config.timeout,
            transport=transport,
        )

    def complete(self, system: str, user: str) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        try:
            response = self._client.post(
                url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json={
                    "model": self.config.model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        except httpx.TimeoutException as exc:
            raise TutorTimeoutError("upstream timed out") from exc
        except httpx.HTTPError as exc:
            raise TutorUpstreamError("upstream request failed") from exc

        if response.status_code >= 400:
            raise TutorUpstreamError(f"upstream status {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise TutorUpstreamError("upstream returned non-JSON") from exc

        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise TutorUpstreamError("upstream returned no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise TutorUpstreamError("upstream returned empty content")
        return content

    def close(self) -> None:
        self._client.close()
