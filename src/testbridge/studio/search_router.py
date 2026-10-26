"""Route search queries to a backend, with fallback only in auto mode."""

from __future__ import annotations

from dataclasses import dataclass

from testbridge.studio.search import SearchError, SearchHit, SearchProvider

ACADEMIC_KEYWORDS = (
    "论文", "综述", "研究", "数据集", "基准", "具身智能", "机器人学习",
    "强化学习", "模仿学习", "大模型", "基础模型", "扩散策略", "仿真到现实",
    "paper", "survey", "benchmark", "dataset", "state of the art", "sota",
    "vla", "vision-language-action", "embodied ai", "robot learning",
    "reinforcement learning", "imitation learning", "foundation model",
    "diffusion policy", "sim-to-real", "sim2real",
)
ACADEMIC_DOMAINS = frozenset({
    "ai", "ml", "research", "embodied-ai", "machine-learning",
    "computer-vision", "nlp",
})
MANUAL_BACKENDS = ("deepseek", "openalex")


@dataclass(frozen=True)
class SearchRoute:
    name: str
    provider: SearchProvider


def is_academic(
    topic: str,
    concept_titles: list[str],
    concept_domains: list[str],
) -> bool:
    text = " ".join([topic, *concept_titles]).lower()
    if any(keyword in text for keyword in ACADEMIC_KEYWORDS):
        return True
    return any(
        domain.strip().lower() in ACADEMIC_DOMAINS
        for domain in concept_domains
    )


class FallbackSearch:
    def __init__(self, primary: SearchProvider, secondary: SearchProvider) -> None:
        self.primary = primary
        self.secondary = secondary

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        try:
            hits = self.primary.search(query, count)
        except SearchError as primary_error:
            try:
                return self.secondary.search(query, count)
            except SearchError as secondary_error:
                raise SearchError(
                    f"primary failed: {primary_error}; "
                    f"secondary failed: {secondary_error}"
                ) from None
        if hits:
            return hits
        try:
            return self.secondary.search(query, count)
        except SearchError as secondary_error:
            raise SearchError(
                f"primary returned no hits; secondary failed: {secondary_error}"
            ) from None

    def fetch(self, url: str) -> str:
        try:
            content = self.primary.fetch(url)
        except SearchError:
            content = ""
        if content:
            return content
        try:
            return self.secondary.fetch(url)
        except SearchError:
            return ""


class SearchRouter:
    def __init__(self, providers: dict[str, SearchProvider]) -> None:
        self.providers = dict(providers)

    def route(
        self,
        backend: str,
        *,
        topic: str,
        concept_titles: list[str],
        concept_domains: list[str],
    ) -> SearchRoute:
        name = str(backend or "auto").strip().lower()
        if name in MANUAL_BACKENDS:
            provider = self.providers.get(name)
            if provider is None:
                raise SearchError(f"backend not configured: {name}")
            return SearchRoute(name, provider)
        return self._auto(topic, concept_titles, concept_domains)

    def route_query(
        self,
        backend: str,
        kind: str,
        *,
        topic: str,
        concept_titles: list[str],
        concept_domains: list[str],
    ) -> SearchRoute:
        """Route one query by its kind; manual backends never fall back."""
        name = str(backend or "auto").strip().lower()
        if name in MANUAL_BACKENDS:
            return self.route(
                name, topic=topic,
                concept_titles=concept_titles, concept_domains=concept_domains,
            )
        primary_name = "openalex" if kind == "academic" else "deepseek"
        secondary_name = (
            "deepseek" if primary_name == "openalex" else "openalex"
        )
        return self._between(primary_name, secondary_name)

    def _between(self, primary_name: str, secondary_name: str) -> SearchRoute:
        primary = self.providers.get(primary_name)
        secondary = self.providers.get(secondary_name)
        if primary is None and secondary is None:
            raise SearchError("no search backend configured")
        if primary is None:
            return SearchRoute(f"auto:{secondary_name}", secondary)
        if secondary is None:
            return SearchRoute(f"auto:{primary_name}", primary)
        return SearchRoute(
            f"auto:{primary_name}->{secondary_name}",
            FallbackSearch(primary, secondary),
        )

    def _auto(
        self,
        topic: str,
        concept_titles: list[str],
        concept_domains: list[str],
    ) -> SearchRoute:
        primary_name = (
            "openalex" if is_academic(topic, concept_titles, concept_domains)
            else "deepseek"
        )
        secondary_name = (
            "deepseek" if primary_name == "openalex" else "openalex"
        )
        return self._between(primary_name, secondary_name)
