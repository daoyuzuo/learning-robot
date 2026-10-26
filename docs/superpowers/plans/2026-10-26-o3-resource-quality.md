# O3 参考资料工程化与可达性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工程来源进得来、链接可用：资源区分 `kind` / `role`，`auto` 检索按查询分流，调研阶段预检链接与付费墙，质量门禁按 required / supplementary 分开计分。

**Architecture:** 契约层只加可选字段（`kind` / `role`），旧包与旧草稿按 `type` 兼容映射；作者层新增 `studio/sources.py`（域名分类与信任下限）与 `studio/verify.py`（可达性/付费墙检测）；`research.py` 产出带类型的查询与带 `kind` / `trust` / `check` 的调研档案；质量层按 `role` 重新定义信任指标并新增来源配比与可达指标。

**Tech Stack:** Python 3.10+、Pydantic v2、httpx、FastAPI + Jinja2、argparse、pytest。

**Spec:** `docs/superpowers/specs/2026-10-26-o3-resource-quality-design.md`

## Global Constraints

- `tb/1` 只新增可选字段；旧内容包与旧草稿不改也能通过 `tb validate`。
- `required` 只允许 A/B；`supplementary` 允许 A/B/C；D 一律拒绝。
- 不自动把 C 级来源升级成 A/B；升级只来自显式域名白名单或 OpenAlex authority。
- 不做付费墙绕过、不抓取付费内容、不伪造访问状态；`paywalled=True` 即视为不可用。
- 手动选择检索后端时绝不静默回退；只有 `auto` 才按查询回退。
- `studio/` 不得 import `mastery` / `schedule` / `learning` / `evidence`。
- `last_verified` 只写真实检查日期；未检查保持空，不再自动填今天。
- 默认 `pytest` 不联网；搜索、HTTP、模型全部用假实现。
- 现有 756 个测试不得回归；两个现有包 `tb validate` 0/0；已发布包 `tb quality` 分数不因新指标变化。
- 代码标识符/注释英文；面向用户的文案中文。

---

## File Structure

- Modify: `src/testbridge/contract/models.py` — `ResourceKind`、`Resource.kind`、`Resource.role`。
- Modify: `src/testbridge/contract/validator.py` — required/supplementary 信任规则。
- Modify: `src/testbridge/content/repository.py` — 旧包 `type → kind` 兼容映射。
- Create: `src/testbridge/studio/sources.py` — 域名分类、白名单信任下限。
- Modify: `src/testbridge/studio/search.py` — `SearchHit` 增加 `is_oa` / `oa_url` / `work_type`。
- Modify: `src/testbridge/studio/search_openalex.py` — OA URL 优先。
- Modify: `src/testbridge/studio/search_router.py` — `route_query` 按查询类型路由。
- Modify: `src/testbridge/studio/research.py` — 带类型查询、逐查询路由、档案字段。
- Create: `src/testbridge/studio/verify.py` — 可达性/付费墙检测与报告。
- Modify: `src/testbridge/studio/gates.py` — 定稿前只阻断 `required` 失败。
- Modify: `src/testbridge/studio/lessons.py` — `role` 校验、`last_verified` 只写真实日期。
- Modify: `src/testbridge/studio/prompts.py` — 资源与检索查询提示词。
- Modify: `src/testbridge/studio/version.py` — `studio/3`。
- Modify: `src/testbridge/quality/provenance.py` — 按 role 计分、来源配比、可达率。
- Modify: `src/testbridge/cli.py` — `tb verify-resources`。
- Modify: `web/studio.py`、`web/app.py` — 逐查询路由、调研预检、过滤后的调研提示词。
- Modify: `README.md`、`docs/ROADMAP.md`、`docs/OPTIMIZATION.md`、spec 状态。

---

### Task 1: 契约新增 `kind` / `role` 与旧包兼容

**Files:**
- Modify: `src/testbridge/contract/models.py`
- Modify: `src/testbridge/contract/validator.py`
- Modify: `src/testbridge/content/repository.py`
- Test: `tests/test_resource_kind.py` (create)

**Interfaces:**
- Produces:
  - `models.ResourceKind = Literal["official_docs","standard","engineering_blog","tutorial","repository","paper","book","video","other"]`
  - `models.Resource.kind: ResourceKind = "other"`；`models.Resource.role: Literal["required","supplementary"] = "required"`
  - `repository.KIND_BY_TYPE: dict[str, str]`
  - `load_pack()` 返回的 `pack.resources[*].kind` 已按旧 `type` 映射。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resource_kind.py
import shutil
from pathlib import Path

import yaml

from testbridge.content.repository import load_pack
from testbridge.contract.models import Resource
from testbridge.contract.validator import validate_pack

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def rewrite_resources(root: Path, **overrides) -> None:
    path = root / "resources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["resources"][0].update(overrides)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_resource_defaults() -> None:
    resource = Resource(
        id="R-1", title="t", url="https://example.com", type="paper", trust="A"
    )
    assert resource.kind == "other"
    assert resource.role == "required"


def test_rejects_unknown_kind() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Resource(
            id="R-1", title="t", url="https://example.com", type="paper",
            trust="A", kind="podcast",
        )


def test_old_pack_kind_derived_from_type(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, type="paper")

    pack = load_pack(root)

    assert pack.resources["DOC-ONE"].kind == "paper"
    assert pack.resources["DOC-ONE"].role == "required"


def test_explicit_kind_wins_over_type(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, type="paper", kind="official_docs")

    pack = load_pack(root)

    assert pack.resources["DOC-ONE"].kind == "official_docs"


def test_validator_rejects_required_c(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, trust="C")

    report = validate_pack(root)

    assert any(issue.code == "resource.required_trust" for issue in report.errors)


def test_validator_allows_supplementary_c(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, trust="C", role="supplementary")

    report = validate_pack(root)

    assert report.errors == []


def test_validator_rejects_d_for_any_role(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, trust="D", role="supplementary")

    report = validate_pack(root)

    assert any(issue.code == "resource.trust" for issue in report.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_resource_kind.py -v`
Expected: FAIL — `ValidationError` for `kind=`（模型尚无该字段），且 `Resource` 无 `kind` 属性。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/contract/models.py`，在 `Trust` 定义后新增：

```python
ResourceKind = Literal[
    "official_docs", "standard", "engineering_blog", "tutorial",
    "repository", "paper", "book", "video", "other",
]
ResourceRole = Literal["required", "supplementary"]
```

`Resource` 增加两个字段（放在 `type` 之后）：

```python
class Resource(StrictModel):
    id: Id
    title: str = Field(min_length=1)
    url: str
    type: str = Field(min_length=1)
    kind: ResourceKind = "other"
    role: ResourceRole = "required"
    trust: Trust
    license: str = ""
    last_verified: str = ""
    coverage: list[Id] = Field(default_factory=list)
    why: str = ""
```

`src/testbridge/contract/validator.py`，在现有 `for resource in resources.values():`（`last_verified` / `license` 告警那个循环）之前加入：

```python
    for resource in resources.values():
        if resource.trust == "D":
            report.errors.append(Issue(
                "resource.trust", f"{resource.id} trust D is not usable"
            ))
        elif resource.role == "required" and resource.trust not in {"A", "B"}:
            report.errors.append(Issue(
                "resource.required_trust",
                f"{resource.id} required resource must be trust A/B",
            ))
```

`src/testbridge/content/repository.py`，模块级加入（同时 `import yaml`）：

```python
KIND_BY_TYPE = {
    "paper": "paper",
    "standard": "standard",
    "standard_draft": "standard",
    "docs": "official_docs",
    "documentation": "official_docs",
    "official-doc": "official_docs",
    "official_docs": "official_docs",
    "repository": "repository",
    "article": "engineering_blog",
    "blog": "engineering_blog",
    "tutorial": "tutorial",
}


def _explicit_kind_ids(path: Path) -> set[str]:
    """Resource ids whose YAML explicitly sets ``kind``."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return set()
    if not isinstance(data, dict):
        return set()
    ids: set[str] = set()
    for item in data.get("resources") or []:
        if not isinstance(item, dict) or "kind" not in item:
            continue
        resource_id = item.get("id")
        if isinstance(resource_id, str):
            ids.add(resource_id)
    return ids
```

在 `load_pack` 中把 `resources=...` 构造改为：

```python
    resources = {item.id: item for item in resources_file.resources}
    if resources_path.is_file():
        explicit = _explicit_kind_ids(resources_path)
        for resource_id, resource in list(resources.items()):
            if resource_id in explicit:
                continue
            mapped = KIND_BY_TYPE.get(resource.type.strip().lower())
            if mapped and mapped != resource.kind:
                resources[resource_id] = resource.model_copy(
                    update={"kind": mapped}
                )
```

并把 `ContentPack(...)` 的 `resources={item.id: item ...}` 改为 `resources=resources`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_resource_kind.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/contract/models.py src/testbridge/contract/validator.py \
  src/testbridge/content/repository.py tests/test_resource_kind.py
git commit -m "feat: add resource kind and role to tb/1"
```

---

### Task 2: 来源分类与信任下限

**Files:**
- Create: `src/testbridge/studio/sources.py`
- Modify: `src/testbridge/studio/search.py`（`SearchHit` 增加 `work_type`）
- Test: `tests/test_studio_sources.py` (create)

**Interfaces:**
- Consumes: `testbridge.studio.search.SearchHit`、`trust_for`。
- Produces:
  - `sources.classify_url(url: str, *, work_type: str | None = None) -> ResourceKind`
  - `sources.classify_hit(hit: SearchHit) -> ResourceKind`
  - `sources.trust_for_hit(hit: SearchHit) -> str`
  - `sources.TRUSTED_B_DOMAINS: frozenset[str]`
  - `SearchHit.work_type: str | None = None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_studio_sources.py
from testbridge.studio.search import SearchHit
from testbridge.studio.sources import classify_hit, classify_url, trust_for_hit


def hit(url: str, authority: int = 1, work_type: str | None = None) -> SearchHit:
    return SearchHit(
        "t", url, "", "", "", authority, work_type=work_type,
    )


def test_classify_official_docs() -> None:
    assert classify_url("https://docs.ros.org/en/rolling/x.html") == "official_docs"
    assert classify_url("https://docs.nvidia.com/isaac/x") == "official_docs"
    assert classify_url("https://ros2.readthedocs.io/en/latest/") == "official_docs"


def test_classify_standard_and_repository() -> None:
    assert classify_url("https://www.omg.org/spec/DDS/") == "standard"
    assert classify_url("https://github.com/ros2/ros2") == "repository"
    assert classify_url("https://github.com/ros2/ros2/tree/master/docs") == (
        "official_docs"
    )


def test_classify_paper_video_and_blog() -> None:
    assert classify_url("https://doi.org/10.1000/x") == "paper"
    assert classify_url("https://arxiv.org/abs/2401.00001") == "paper"
    assert classify_url("https://youtu.be/abc") == "video"
    assert classify_url("https://example.com/blog/executors") == "engineering_blog"
    assert classify_url("https://example.com/tutorial/getting-started") == "tutorial"
    assert classify_url("not-a-url") == "other"


def test_work_type_decides_paper() -> None:
    assert classify_url("https://example.com/x", work_type="preprint") == "paper"
    assert classify_url("https://example.com/x", work_type="book") == "book"


def test_classify_hit_uses_work_type() -> None:
    assert classify_hit(hit("https://acme.example/p", work_type="article")) == "paper"


def test_trusted_domain_raises_c_to_b() -> None:
    assert trust_for_hit(hit("https://docs.ros.org/x", authority=1)) == "B"
    assert trust_for_hit(hit("https://medium.com/@a/x", authority=1)) == "C"
    assert trust_for_hit(hit("https://docs.ros.org/x", authority=3)) == "A"


def test_retracted_stays_d() -> None:
    assert trust_for_hit(hit("https://docs.ros.org/x", authority=-1)) == "D"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_studio_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: testbridge.studio.sources`，且 `SearchHit` 不接受 `work_type`。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/studio/search.py`：`SearchHit` 增加字段（放末尾，保持位置参数兼容）：

```python
@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    summary: str
    content: str
    authority: int
    date: str | None = None
    is_oa: bool = False
    oa_url: str | None = None
    work_type: str | None = None
```

`src/testbridge/studio/sources.py`：

```python
"""Deterministic source classification and trust floor for research hits.

The domain lists are author-layer rules: they are not written into content
packs and never take part in grading.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from testbridge.contract.models import ResourceKind
from testbridge.studio.search import SearchHit, trust_for

OFFICIAL_DOC_DOMAINS = frozenset({
    "docs.ros.org", "docs.ros2.org", "design.ros2.org",
    "docs.nvidia.com", "developer.nvidia.com", "docs.openvino.ai",
    "docs.python.org", "docs.docker.com", "kubernetes.io", "readthedocs.io",
})
STANDARD_DOMAINS = frozenset({
    "omg.org", "dds-foundation.org", "iso.org", "iec.ch", "nist.gov",
})
REPOSITORY_DOMAINS = frozenset({"github.com", "gitlab.com"})
PAPER_DOMAINS = frozenset({"doi.org", "arxiv.org", "openalex.org"})
VIDEO_DOMAINS = frozenset({"youtube.com", "youtu.be", "vimeo.com", "bilibili.com"})
PRACTICE_DOMAINS = frozenset({
    "discourse.ros.org", "ros.org", "openrobotics.org",
    "medium.com", "dev.to",
})
TRUSTED_B_DOMAINS = (
    OFFICIAL_DOC_DOMAINS | STANDARD_DOMAINS | REPOSITORY_DOMAINS | PRACTICE_DOMAINS
)
PAPER_WORK_TYPES = frozenset({
    "article", "review", "book-chapter", "proceedings-article", "preprint",
    "dataset", "dissertation", "report",
})


def _host(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    return (parts.hostname or "").lower()


def _path(url: str) -> str:
    try:
        return urlsplit(url.strip()).path.lower()
    except ValueError:
        return ""


def _matches(host: str, domains: frozenset[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def classify_url(url: str, *, work_type: str | None = None) -> ResourceKind:
    host = _host(url)
    if not host:
        return "other"
    kind = (work_type or "").strip().lower()
    if kind == "book":
        return "book"
    if kind in PAPER_WORK_TYPES:
        return "paper"
    if _matches(host, PAPER_DOMAINS):
        return "paper"
    if _matches(host, STANDARD_DOMAINS):
        return "standard"
    if _matches(host, VIDEO_DOMAINS):
        return "video"
    if _matches(host, OFFICIAL_DOC_DOMAINS):
        return "official_docs"
    if _matches(host, REPOSITORY_DOMAINS):
        path = _path(url)
        if "/docs" in path or "readme" in path:
            return "official_docs"
        return "repository"
    path = _path(url)
    if "/tutorial" in path or "/how-to" in path or "/getting-started" in path:
        return "tutorial"
    if "/blog" in path or "/posts/" in path or "/article" in path:
        return "engineering_blog"
    return "other"


def classify_hit(hit: SearchHit) -> ResourceKind:
    return classify_url(hit.url, work_type=hit.work_type)


def trust_for_hit(hit: SearchHit) -> str:
    """Base trust from authority, raised to B only for whitelisted domains."""
    base = trust_for(hit.authority)
    if base == "D":
        return "D"
    if base == "C" and _matches(_host(hit.url), TRUSTED_B_DOMAINS):
        return "B"
    return base
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_studio_sources.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/sources.py src/testbridge/studio/search.py \
  tests/test_studio_sources.py
git commit -m "feat: classify research sources and apply a trust floor"
```

---

### Task 3: OpenAlex 优先给出可访问链接

**Files:**
- Modify: `src/testbridge/studio/search_openalex.py`
- Test: `tests/test_search_openalex.py`

**Interfaces:**
- Produces: `SearchHit.url` 选择顺序为 OA URL → landing page → DOI → OpenAlex work id；`SearchHit.is_oa` / `oa_url` / `work_type` 有值。

- [ ] **Step 1: Update the failing tests**

在 `tests/test_search_openalex.py` 中：

1. `test_search_request_and_mapping` 改为断言 OA 链接优先：

```python
    assert hits[0].url == "https://oa.example/p"
    assert hits[0].oa_url == "https://oa.example/p"
    assert hits[0].is_oa is True
    assert hits[0].work_type == "article"
```

2. 新增两个测试：

```python
def test_oa_url_wins_over_doi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [work()]})

    hits = client(handler).search("q")

    assert hits[0].url == "https://oa.example/p"


def test_doi_used_when_no_oa_or_landing() -> None:
    ok = work(primary_location={}, open_access={})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [ok]})

    hits = client(handler).search("q")

    assert hits[0].url == "https://doi.org/10.1000/x"
    assert hits[0].is_oa is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_search_openalex.py -v`
Expected: FAIL — 当前仍返回 DOI 链接，`is_oa` / `oa_url` / `work_type` 为默认值。

- [ ] **Step 3: Write minimal implementation**

在 `src/testbridge/studio/search_openalex.py` 中新增 helper 并调整顺序：

```python
def _oa_url(work: dict) -> str:
    open_access = work.get("open_access")
    if isinstance(open_access, dict):
        value = open_access.get("oa_url")
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return ""


def _url_for(work: dict) -> str:
    oa_url = _oa_url(work)
    if oa_url:
        return oa_url
    primary = work.get("primary_location")
    if isinstance(primary, dict):
        landing = primary.get("landing_page_url")
        if isinstance(landing, str) and landing.startswith(("http://", "https://")):
            return landing
    doi_url = _doi_url(work.get("doi"))
    if doi_url:
        return doi_url
    work_id = work.get("id")
    if isinstance(work_id, str) and work_id.startswith(("http://", "https://")):
        return work_id
    return ""


def _is_oa(work: dict) -> bool:
    open_access = work.get("open_access")
    if isinstance(open_access, dict) and open_access.get("is_oa") is True:
        return True
    return bool(_oa_url(work))


def _work_type(work: dict) -> str | None:
    value = work.get("type")
    return str(value) if isinstance(value, str) and value else None
```

`_to_hit` 改为：

```python
def _to_hit(work: dict) -> SearchHit | None:
    if not isinstance(work, dict):
        return None
    url = _url_for(work)
    if not url:
        return None
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    title = work.get("display_name") or work.get("title") or ""
    return SearchHit(
        title=str(title),
        url=url,
        snippet=abstract[:300],
        summary=abstract,
        content=abstract,
        authority=authority_for(work),
        date=_date_for(work),
        is_oa=_is_oa(work),
        oa_url=_oa_url(work) or None,
        work_type=_work_type(work),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_search_openalex.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/search_openalex.py tests/test_search_openalex.py
git commit -m "feat: prefer open access links from OpenAlex"
```

---

### Task 4: 带类型的查询 + 按查询路由 + 档案字段

**Files:**
- Modify: `src/testbridge/studio/search_router.py`
- Modify: `src/testbridge/studio/research.py`
- Test: `tests/test_search_router.py`、`tests/test_studio_research.py`

**Interfaces:**
- Consumes: `sources.classify_hit`、`sources.trust_for_hit`、`verify.ResourceCheck`（Task 5 定义，本任务先用鸭子类型：`check.as_dict()`）。
- Produces:
  - `SearchRouter.route_query(backend: str, kind: str, *, topic: str, concept_titles: list[str], concept_domains: list[str]) -> SearchRoute`
  - `research.ResearchQuery(text: str, kind: str)`
  - `research.build_queries(lesson, concept_titles, budget) -> list[ResearchQuery]`
  - `research.run_research(lesson, concept_titles, search=None, budget=1, progress=None, backend="", *, route_for=None) -> ResearchResult`
  - `ResearchResult.query_log: list[dict]`
  - `research.write_research(store, draft_id, lesson, result, *, checks=None) -> None`
  - `research.render_research_for_prompt(payload: str) -> str`
  - `research.usable_urls_from_payload(payload: str) -> set[str] | None`

- [ ] **Step 1: Write the failing tests**

在 `tests/test_search_router.py` 追加：

```python
def test_route_query_academic_uses_openalex() -> None:
    router = SearchRouter({
        "deepseek": FakeSearch("deepseek"),
        "openalex": FakeSearch("openalex"),
    })

    route = router.route_query(
        "auto", "academic", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:openalex->deepseek"


def test_route_query_engineering_uses_deepseek() -> None:
    router = SearchRouter({
        "deepseek": FakeSearch("deepseek"),
        "openalex": FakeSearch("openalex"),
    })

    route = router.route_query(
        "auto", "engineering", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:deepseek->openalex"


def test_route_query_manual_never_falls_back() -> None:
    router = SearchRouter({"deepseek": FakeSearch("deepseek")})

    route = router.route_query(
        "deepseek", "academic", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "deepseek"
    assert isinstance(route.provider, FakeSearch)
```

在 `tests/test_studio_research.py` 中：

1. `test_build_queries_respects_budget_and_includes_site_query` 改为：

```python
def test_build_queries_respects_budget_and_includes_site_query() -> None:
    queries = build_queries(LESSON, ["执行器基础", "回调组"], budget=4)
    texts = [item.text for item in queries]
    assert texts[0] == "ros executors"
    assert any("site:docs.ros.org" in item for item in texts)
    assert len(queries) <= 4
    assert {item.kind for item in queries} <= {"academic", "engineering", "official"}
```

2. 追加：

```python
def test_build_queries_mixes_kinds() -> None:
    queries = build_queries(LESSON, ["执行器基础"], budget=8)
    kinds = {item.kind for item in queries}
    assert "engineering" in kinds
    assert "official" in kinds


def test_run_research_records_query_log() -> None:
    result = run_research(LESSON, ["执行器基础"], FakeSearch(), budget=3)

    assert result.query_log
    assert set(result.query_log[0]) == {"query", "kind", "backend"}


def test_run_research_uses_route_for_each_query() -> None:
    seen: list[str] = []
    deepseek = FakeSearch()
    openalex = FakeSearch()
    router = SearchRouter({"deepseek": deepseek, "openalex": openalex})

    class RecordingRouter(SearchRouter):
        def route_query(self, backend, kind, **kwargs):
            seen.append(kind)
            return super().route_query(backend, kind, **kwargs)

    result = run_research(
        LESSON, ["执行器基础"], budget=3,
        route_for=lambda kind: RecordingRouter({
            "deepseek": deepseek, "openalex": openalex,
        }).route_query(
            "auto", kind, topic="t", concept_titles=[], concept_domains=[]
        ),
    )

    assert seen
    assert set(result.query_log[0]) == {"query", "kind", "backend"}


def test_write_research_records_kind_trust_and_check(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    result = run_research(LESSON, ["执行器基础"], FakeSearch(), budget=1)

    class FakeCheck:
        def as_dict(self):
            return {"url": "https://x", "status": 200, "paywalled": False}

    checks = {hit.url: FakeCheck() for hit in result.hits}
    write_research(store, "demo", LESSON, result, checks=checks)

    payload = json.loads(store.read("demo", "research/L-1.json"))
    first = payload["hits"][0]
    assert first["kind"] in {
        "official_docs", "standard", "engineering_blog", "tutorial",
        "repository", "paper", "book", "video", "other",
    }
    assert first["trust"] in {"A", "B", "C", "D"}
    assert first["check"]["status"] == 200


def test_render_research_for_prompt_drops_unusable_hits() -> None:
    payload = json.dumps({
        "hits": [
            {"title": "ok", "url": "https://ok.example",
             "check": {"status": 200, "paywalled": False}},
            {"title": "wall", "url": "https://wall.example",
             "check": {"status": 200, "paywalled": True}},
        ]
    })

    text = render_research_for_prompt(payload)

    assert "https://ok.example" in text
    assert "wall.example" not in text


def test_usable_urls_from_payload() -> None:
    payload = json.dumps({
        "hits": [
            {"url": "https://ok.example",
             "check": {"status": 200, "paywalled": False}},
            {"url": "https://bad.example",
             "check": {"status": 404, "paywalled": False}},
        ]
    })

    assert usable_urls_from_payload(payload) == {"https://ok.example"}
    assert usable_urls_from_payload('{"hits": [{"url": "https://x"}]}') is None
    assert usable_urls_from_payload("not json") is None
```

并补充 imports：

```python
from testbridge.studio.research import (
    ResearchResult, build_queries, render_research_for_prompt, run_research,
    usable_urls_from_payload, write_research,
)
from testbridge.studio.search import SearchHit
from testbridge.studio.search_router import SearchRouter
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_search_router.py tests/test_studio_research.py -v`
Expected: FAIL — `route_query` 不存在，`build_queries` 返回 `str`，`query_log` / 新函数不存在。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/studio/search_router.py`：把 `_auto` 拆成可复用的组合，并新增 `route_query`：

```python
    def route_query(
        self,
        backend: str,
        kind: str,
        *,
        topic: str,
        concept_titles: list[str],
        concept_domains: list[str],
    ) -> SearchRoute:
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
```

`src/testbridge/studio/research.py`：完整替换文件头部与查询/运行/写入函数：

```python
"""Search orchestration and research dossier.

The dossier is source evidence: it is written once per lesson and never edited
by the model in later steps.
"""

from __future__ import annotations

import html as html_lib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from testbridge.studio.outline import LessonPlan
from testbridge.studio.search import SearchHit, SearchProvider, trust_for
from testbridge.studio.search_router import ACADEMIC_KEYWORDS, SearchRoute
from testbridge.studio.sources import classify_hit, trust_for_hit
from testbridge.studio.store import DraftStore

SITE_QUERY = "site:docs.ros.org OR site:docs.ros2.org"
CONTENT_LIMIT = 4000
QUERY_KINDS = ("academic", "engineering", "official")
OFFICIAL_HINTS = (
    "site:", "docs.", "documentation", "官方文档", "标准", "spec", "reference",
)
ENGINEERING_HINTS = (
    "best practice", "tutorial", "how to", "guide", "教程", "实践", "排查",
    "测试", "调试",
)


@dataclass(frozen=True)
class ResearchQuery:
    text: str
    kind: str


@dataclass(frozen=True)
class ResearchResult:
    lesson_id: str
    queries: list[str]
    hits: list[SearchHit]
    errors: list[str] = field(default_factory=list)
    searches: int = 0
    backend: str = ""
    query_log: list[dict] = field(default_factory=list)


def classify_query(text: str) -> str:
    lowered = text.lower()
    if any(hint in lowered for hint in ACADEMIC_KEYWORDS):
        return "academic"
    if any(hint in lowered for hint in OFFICIAL_HINTS):
        return "official"
    return "engineering"


def build_queries(
    lesson: LessonPlan, concept_titles: list[str], budget: int
) -> list[ResearchQuery]:
    candidates = [
        *lesson.queries, lesson.title,
        f"{lesson.title} {SITE_QUERY}", *concept_titles,
    ]
    buckets: dict[str, list[ResearchQuery]] = {kind: [] for kind in QUERY_KINDS}
    seen: set[str] = set()
    for text in candidates:
        if not text or text in seen:
            continue
        seen.add(text)
        kind = classify_query(text)
        buckets[kind].append(ResearchQuery(text, kind))
    limit = max(1, budget)
    ordered: list[ResearchQuery] = []
    while len(ordered) < limit and any(buckets.values()):
        for kind in QUERY_KINDS:
            if len(ordered) >= limit:
                break
            if buckets[kind]:
                ordered.append(buckets[kind].pop(0))
    return ordered


def run_research(
    lesson: LessonPlan,
    concept_titles: list[str],
    search: SearchProvider | None = None,
    budget: int = 1,
    progress: Callable[[int, int, int], None] | None = None,
    backend: str = "",
    *,
    route_for: Callable[[str], SearchRoute] | None = None,
) -> ResearchResult:
    queries = build_queries(lesson, concept_titles, budget)
    hits: list[SearchHit] = []
    seen: set[str] = set()
    errors: list[str] = []
    names: list[str] = []
    query_log: list[dict] = []
    for index, query in enumerate(queries, start=1):
        if route_for is not None:
            route = route_for(query.kind)
            provider = route.provider
            name = route.name
        elif search is not None:
            provider = search
            name = backend
        else:
            raise TypeError("run_research requires search= or route_for=")
        names.append(name)
        try:
            for hit in provider.search(query.text, count=8):
                if hit.url in seen:
                    continue
                seen.add(hit.url)
                hits.append(hit)
        except Exception as exc:  # noqa: BLE001 - keep research going
            errors.append(f"{query.text}: {type(exc).__name__}")
        query_log.append(
            {"query": query.text, "kind": query.kind, "backend": name}
        )
        if progress is not None:
            progress(index, len(queries), len(hits))
    resolved_backend = backend or ",".join(dict.fromkeys(names))
    return ResearchResult(
        lesson_id=lesson.lesson_id,
        queries=[item.text for item in queries],
        hits=hits,
        errors=errors,
        searches=len(queries),
        backend=resolved_backend,
        query_log=query_log,
    )
```

`render_research_html` 的命中行改为带 kind 与检查状态：

```python
def _check_label(check: object) -> str:
    if not isinstance(check, dict):
        return "未检查"
    if check.get("paywalled"):
        return "付费墙"
    status = check.get("status")
    if isinstance(status, int) and status >= 400:
        return f"HTTP {status}"
    if check.get("error"):
        return "不可达"
    return "可达"


def render_research_html(lesson: LessonPlan, result: ResearchResult) -> str:
    rows = []
    for hit in result.hits:
        rows.append(
            f'<li class="tb-hit"><a href="{html_lib.escape(hit.url)}">'
            f"{html_lib.escape(hit.title or hit.url)}</a> "
            f'<span class="tb-trust">{trust_for(hit.authority)}</span> '
            f'<span class="tb-kind">{classify_hit(hit)}</span>'
            f"<p>{html_lib.escape(hit.summary or hit.snippet)}</p></li>"
        )
    errors = "".join(
        f"<li>{html_lib.escape(item)}</li>" for item in result.errors
    )
    return (
        '<article class="tb-research">'
        f"<h1>调研档案：{html_lib.escape(lesson.title)}</h1>"
        f"<p>查询 {len(result.queries)} 次，命中 {len(result.hits)} 条。</p>"
        '<ul class="tb-queries">'
        + "".join(f"<li>{html_lib.escape(q)}</li>" for q in result.queries)
        + "</ul>"
        f'<ul class="tb-hits">{"".join(rows)}</ul>'
        + (f'<ul class="tb-errors">{errors}</ul>' if errors else "")
        + "</article>"
    )
```

`write_research` 与新增的提示词辅助：

```python
def write_research(
    store: DraftStore,
    draft_id: str,
    lesson: LessonPlan,
    result: ResearchResult,
    *,
    checks: dict | None = None,
) -> None:
    hits = []
    for hit in result.hits:
        item = {
            "title": hit.title, "url": hit.url, "snippet": hit.snippet,
            "summary": hit.summary, "content": hit.content[:CONTENT_LIMIT],
            "authority": hit.authority, "date": hit.date,
            "trust": trust_for_hit(hit),
            "kind": classify_hit(hit),
        }
        check = checks.get(hit.url) if checks else None
        if check is not None:
            item["check"] = check.as_dict()
        hits.append(item)
    payload = {
        "lesson_id": result.lesson_id,
        "queries": result.queries,
        "searches": result.searches,
        "backend": result.backend,
        "errors": result.errors,
        "query_log": result.query_log,
        "hits": hits,
    }
    store.write(
        draft_id, f"research/{result.lesson_id}.json",
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
    store.write(
        draft_id, f"research/{result.lesson_id}.html",
        render_research_html(lesson, result),
    )


def _check_ok(check: dict) -> bool:
    status = check.get("status")
    return (
        not check.get("error")
        and isinstance(status, int)
        and status < 400
        and not check.get("paywalled")
    )


def render_research_for_prompt(payload: str) -> str:
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    lines = []
    for hit in data.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        check = hit.get("check")
        if isinstance(check, dict) and not _check_ok(check):
            continue
        lines.append(json.dumps({
            key: hit.get(key)
            for key in (
                "title", "url", "summary", "content",
                "authority", "trust", "kind", "check",
            )
        }, ensure_ascii=False))
    return "\n".join(lines)


def usable_urls_from_payload(payload: str) -> set[str] | None:
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    hits = [hit for hit in data.get("hits") or [] if isinstance(hit, dict)]
    if not any(isinstance(hit.get("check"), dict) for hit in hits):
        return None
    return {
        str(hit.get("url") or "")
        for hit in hits
        if isinstance(hit.get("check"), dict) and _check_ok(hit["check"])
    }
```

（`Path` 在此文件中未使用则不要 import，保持 flake 干净。）

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_search_router.py tests/test_studio_research.py -v`
Expected: PASS（全部通过）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/search_router.py src/testbridge/studio/research.py \
  tests/test_search_router.py tests/test_studio_research.py
git commit -m "feat: route research queries by kind"
```

---

### Task 5: 可达性与付费墙检测 + `tb verify-resources`

**Files:**
- Create: `src/testbridge/studio/verify.py`
- Modify: `src/testbridge/studio/gates.py`
- Modify: `src/testbridge/cli.py`
- Test: `tests/test_studio_verify.py` (create)、`tests/test_cli_verify.py` (create)

**Interfaces:**
- Produces:
  - `verify.ResourceCheck`（`url, status, final_url, content_length, paywalled, error`；`ok` 属性；`as_dict()` / `from_dict()`）
  - `verify.check_url(client, url) -> ResourceCheck`
  - `verify.check_urls(client, urls, *, limit=10) -> dict[str, ResourceCheck]`
  - `verify.usable_urls(checks) -> set[str]`
  - `verify.reason(check) -> str`
  - `gates.verify_resources(resources, client=None)` 只返回 `required` 的失败
  - `cli.main(["verify-resources", "<pack>"]) -> 0 | 1 | 2`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_studio_verify.py
from testbridge.studio.verify import ResourceCheck, check_url, check_urls, reason, usable_urls


class FakeResponse:
    def __init__(self, status: int, url: str = "", text: str = "", ctype: str = ""):
        self.status_code = status
        self.url = url
        self.text = text
        self.headers = {"content-type": ctype} if ctype else {}


class FakeClient:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, **kwargs):
        return self.responses.get(url, FakeResponse(200, url, "x" * 2000))


def test_ok_page() -> None:
    client = FakeClient({"https://ok": FakeResponse(200, "https://ok", "x" * 2000)})
    check = check_url(client, "https://ok")
    assert check.ok is True
    assert check.status == 200


def test_http_error() -> None:
    client = FakeClient({"https://bad": FakeResponse(404, "https://bad", "no")})
    check = check_url(client, "https://bad")
    assert check.ok is False
    assert reason(check) == "HTTP 404"


def test_login_redirect_is_paywalled() -> None:
    client = FakeClient({
        "https://paper": FakeResponse(
            200, "https://publisher.example/login?next=/paper", "x" * 2000
        ),
    })
    check = check_url(client, "https://paper")
    assert check.paywalled is True
    assert check.ok is False


def test_paywall_phrase_is_flagged() -> None:
    client = FakeClient({
        "https://paper": FakeResponse(
            200, "https://paper", "Subscribe to continue reading. " + "x" * 2000
        ),
    })
    assert check_url(client, "https://paper").paywalled is True


def test_short_page_is_flagged() -> None:
    client = FakeClient({
        "https://thin": FakeResponse(200, "https://thin", "short", "text/html"),
    })
    assert check_url(client, "https://thin").paywalled is True


def test_forbidden_status_is_paywalled() -> None:
    client = FakeClient({"https://x": FakeResponse(403, "https://x", "x" * 2000)})
    assert check_url(client, "https://x").paywalled is True


def test_network_error_is_recorded() -> None:
    class Boom:
        def get(self, url: str, **kwargs):
            raise RuntimeError("boom")

    check = check_url(Boom(), "https://x")
    assert check.ok is False
    assert check.error == "RuntimeError"


def test_check_urls_respects_limit_and_dedupes() -> None:
    client = FakeClient({})
    checks = check_urls(client, ["https://a", "https://a", "https://b"], limit=2)
    assert set(checks) == {"https://a", "https://b"}
    assert usable_urls(checks) == {"https://a", "https://b"}


def test_check_round_trips_through_dict() -> None:
    check = ResourceCheck("https://x", 200, "https://x", 10, False, "")
    assert ResourceCheck.from_dict(check.as_dict()) == check
```

```python
# tests/test_cli_verify.py
from pathlib import Path

from testbridge.cli import main
from testbridge.studio.verify import ResourceCheck

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def fake_check(ok: bool):
    def check_url(client, url):
        return ResourceCheck(url, 200 if ok else 404, url, 100, False, "")
    return check_url


def test_verify_resources_ok(monkeypatch, capsys) -> None:
    monkeypatch.setattr("testbridge.cli.check_url", fake_check(True))
    monkeypatch.setattr(
        "testbridge.cli.httpx.Client",
        lambda **kwargs: type("C", (), {"close": lambda self: None})(),
    )

    code = main(["verify-resources", str(FIXTURE)])

    out = capsys.readouterr().out
    assert code == 0
    assert "DOC-ONE" in out
    assert "OK" in out


def test_verify_resources_failure_is_nonzero(monkeypatch, capsys) -> None:
    monkeypatch.setattr("testbridge.cli.check_url", fake_check(False))
    monkeypatch.setattr(
        "testbridge.cli.httpx.Client",
        lambda **kwargs: type("C", (), {"close": lambda self: None})(),
    )

    code = main(["verify-resources", str(FIXTURE)])

    out = capsys.readouterr().out
    assert code == 1
    assert "DOC-ONE" in out
    assert "HTTP 404" in out


def test_verify_resources_invalid_pack(monkeypatch, capsys) -> None:
    code = main(["verify-resources", "does-not-exist"])

    assert code == 2
    assert "ERROR" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_studio_verify.py tests/test_cli_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: testbridge.studio.verify`，且 `verify-resources` 未注册。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/studio/verify.py`：

```python
"""Reachability and paywall checks for lesson resources.

Detection only: the module never tries to bypass a wall and never pretends a
resource was reachable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

MIN_CONTENT_LENGTH = 800
MAX_BYTES = 200_000
PAYWALL_STATUS = frozenset({401, 402, 403})
PAYWALL_PATH = re.compile(
    r"(log-?in|sign-?in|sign-?up|subscribe|purchase|paywall|register)", re.I
)
PAYWALL_PHRASES = (
    "subscribe to continue", "purchase this", "access denied",
    "sign in to continue", "already a subscriber",
)


@dataclass(frozen=True)
class ResourceCheck:
    url: str
    status: int | None
    final_url: str
    content_length: int
    paywalled: bool
    error: str = ""

    @property
    def ok(self) -> bool:
        return (
            not self.error
            and self.status is not None
            and self.status < 400
            and not self.paywalled
        )

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "status": self.status,
            "final_url": self.final_url,
            "content_length": self.content_length,
            "paywalled": self.paywalled,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceCheck":
        return cls(
            url=str(data.get("url") or ""),
            status=data.get("status"),
            final_url=str(data.get("final_url") or ""),
            content_length=int(data.get("content_length") or 0),
            paywalled=bool(data.get("paywalled")),
            error=str(data.get("error") or ""),
        )


def _paywalled(status: int, final_url: str, text: str, ctype: str) -> bool:
    if status in PAYWALL_STATUS:
        return True
    try:
        path = urlsplit(final_url).path or ""
    except ValueError:
        path = ""
    if PAYWALL_PATH.search(path):
        return True
    lowered = text.lower()
    if any(phrase in lowered for phrase in PAYWALL_PHRASES):
        return True
    if text and "html" in ctype and len(text) < MIN_CONTENT_LENGTH:
        return True
    return False


def check_url(client, url: str) -> ResourceCheck:
    try:
        response = client.get(url, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - any transport error is a failure
        return ResourceCheck(url, None, url, 0, False, type(exc).__name__)
    status = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    text = str(getattr(response, "text", "") or "")[:MAX_BYTES]
    headers = getattr(response, "headers", {}) or {}
    ctype = str(headers.get("content-type", "") or "").lower()
    return ResourceCheck(
        url=url,
        status=status,
        final_url=final_url,
        content_length=len(text),
        paywalled=_paywalled(status, final_url, text, ctype),
        error="",
    )


def check_urls(client, urls, *, limit: int = 10) -> dict[str, ResourceCheck]:
    checks: dict[str, ResourceCheck] = {}
    for url in list(urls)[:limit]:
        if not url or url in checks:
            continue
        checks[url] = check_url(client, url)
    return checks


def usable_urls(checks: dict[str, ResourceCheck]) -> set[str]:
    return {url for url, check in checks.items() if check.ok}


def reason(check: ResourceCheck) -> str:
    if check.error:
        return check.error
    if check.status is not None and check.status >= 400:
        return f"HTTP {check.status}"
    if check.paywalled:
        return "paywalled"
    return "unreachable"
```

`src/testbridge/studio/gates.py`：替换 `verify_resources` 实现并 import：

```python
from testbridge.studio.verify import check_url, reason
```

```python
def verify_resources(resources, client=None) -> list[str]:
    """Return failures for required resources; supplementary links never block."""
    owned = client is None
    client = client or httpx.Client(timeout=10.0, follow_redirects=True)
    errors = []
    try:
        for resource in resources:
            role = str(resource.get("role") or "required")
            if role != "required":
                continue
            resource_id = resource.get("id", "?")
            check = check_url(client, str(resource.get("url") or ""))
            if check.ok:
                continue
            errors.append(f"{resource_id}: {reason(check)}")
    finally:
        if owned:
            client.close()
    return errors
```

`src/testbridge/cli.py`：import 区加 `httpx`、`ContentValidationError`、`check_url`、`reason`：

```python
import httpx

from testbridge.content.repository import (
    ContentValidationError, list_packs, load_pack,
)
from testbridge.studio.verify import check_url, reason
```

子命令注册（放在 `doctor` 之后）：

```python
    verify = sub.add_parser("verify-resources", help="check resource links")
    verify.add_argument("pack")
```

分派分支（放在 `doctor` / `env` 之后）：

```python
    if args.command == "verify-resources":
        return _cmd_verify_resources(args)
```

处理函数：

```python
def _cmd_verify_resources(args) -> int:
    pack_dir = Path(args.pack)
    try:
        pack = load_pack(pack_dir)
    except ContentValidationError as exc:
        print(
            f"ERROR verify-resources: pack is invalid "
            f"({len(exc.report.errors)} error(s))",
            file=sys.stderr,
        )
        return 2
    client = httpx.Client(timeout=10.0, follow_redirects=True)
    failures = 0
    try:
        for resource in sorted(pack.resources.values(), key=lambda item: item.id):
            check = check_url(client, resource.url)
            if check.ok:
                print(f"OK    {resource.id} {resource.url}")
                continue
            if resource.role == "required":
                failures += 1
                print(f"ERROR {resource.id} {resource.url}: {reason(check)}")
            else:
                print(f"WARN  {resource.id} {resource.url}: {reason(check)}")
    finally:
        client.close()
    return 1 if failures else 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_studio_verify.py tests/test_cli_verify.py tests/test_studio_gates.py -v`
Expected: PASS（含既有 gates 测试，`DOC-2: HTTP 404` 原样保留）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/verify.py src/testbridge/studio/gates.py \
  src/testbridge/cli.py tests/test_studio_verify.py tests/test_cli_verify.py
git commit -m "feat: verify resource reachability and paywalls"
```

---

### Task 6: 写课解析按 role 校验，`last_verified` 只写真实日期

**Files:**
- Modify: `src/testbridge/studio/lessons.py`
- Test: `tests/test_studio_lessons.py`

**Interfaces:**
- Produces: `parse_lesson_json(raw, lesson, concept_ids, *, usable_urls: set[str] | None = None) -> LessonOutput`
- 行为：`required` 只允许 A/B；`supplementary` 允许 A/B/C；D 一律拒绝；`last_verified` 仅在 URL 出现在 `usable_urls` 且检查通过时写当天，否则为空。

- [ ] **Step 1: Write the failing tests**

在 `tests/test_studio_lessons.py` 追加：

```python
def _payload(**resource_overrides) -> str:
    resource = {**PAYLOAD["resources"][0], **resource_overrides}
    return json.dumps({**PAYLOAD, "resources": [resource]})


def test_required_c_is_rejected() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload(trust="C"), LESSON, {"executor-basics"}
        )


def test_supplementary_c_is_allowed() -> None:
    output = parse_lesson_json(
        _payload(trust="C", role="supplementary"), LESSON, {"executor-basics"}
    )
    assert output.resources[0]["role"] == "supplementary"
    assert output.resources[0]["trust"] == "C"


def test_d_trust_is_rejected_for_supplementary() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload(trust="D", role="supplementary"),
            LESSON, {"executor-basics"},
        )


def test_last_verified_is_cleared_without_a_check() -> None:
    output = parse_lesson_json(
        _payload(), LESSON, {"executor-basics"}
    )
    assert output.resources[0]["last_verified"] == ""


def test_last_verified_is_set_for_checked_url() -> None:
    output = parse_lesson_json(
        _payload(), LESSON, {"executor-basics"},
        usable_urls={"https://docs.ros.org/x"},
    )
    assert output.resources[0]["last_verified"]


def test_required_must_pass_preflight() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload(), LESSON, {"executor-basics"},
            usable_urls={"https://other.example"},
        )


def test_missing_kind_is_derived_from_type() -> None:
    output = parse_lesson_json(
        _payload(type="paper"), LESSON, {"executor-basics"}
    )
    assert output.resources[0]["kind"] == "paper"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_studio_lessons.py -v`
Expected: FAIL — supplementary C 被拒；`usable_urls` 参数不存在；`last_verified` 被自动填成今天。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/studio/lessons.py`：import 区增加
`from testbridge.content.repository import KIND_BY_TYPE`，并替换常量与
`_parse_resources`：

```python
ALLOWED_REQUIRED_TRUST = {"A", "B"}
ALLOWED_SUPPLEMENTARY_TRUST = {"A", "B", "C"}


def _parse_resources(
    items: object,
    concept_ids: set[str],
    usable_urls: set[str] | None = None,
) -> list[dict]:
    if not isinstance(items, list):
        raise LessonError("resources 必须是数组")
    parsed: list[dict] = []
    seen: set[str] = set()
    today = datetime.now(timezone.utc).date().isoformat()
    verified = set(usable_urls or ())
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise LessonError("资源缺少 id")
        resource_id = item["id"]
        if resource_id in seen:
            raise LessonError(f"资源 id 重复：{resource_id}")
        role = str(item.get("role") or "required")
        trust = item.get("trust")
        if trust == "D":
            raise LessonError(f"资源 trust D 不可用：{resource_id}")
        if role == "required" and trust not in ALLOWED_REQUIRED_TRUST:
            raise LessonError(f"required 资源只允许 A/B：{resource_id}")
        if role == "supplementary" and trust not in ALLOWED_SUPPLEMENTARY_TRUST:
            raise LessonError(f"supplementary 资源只允许 A/B/C：{resource_id}")
        try:
            resource = Resource.model_validate(item)
        except ValidationError as exc:
            raise LessonError(
                f"资源 {resource_id} 不符合 tb/1：{_first_error(exc)}"
            ) from None
        for concept_id in resource.coverage:
            if concept_id not in concept_ids:
                raise LessonError(f"资源覆盖了不存在的概念：{concept_id}")
        if (
            usable_urls is not None
            and resource.role == "required"
            and resource.url not in verified
        ):
            raise LessonError(f"required 资源未通过可达性检查：{resource_id}")
        data = resource.model_dump(exclude_none=True)
        if "kind" not in item:
            data["kind"] = KIND_BY_TYPE.get(
                resource.type.strip().lower(), "other"
            )
        data["last_verified"] = today if resource.url in verified else ""
        parsed.append(data)
        seen.add(resource_id)
    return parsed
```

`parse_lesson_json` 增加参数并透传：

```python
def parse_lesson_json(
    raw: str,
    lesson: LessonPlan,
    concept_ids: set[str],
    *,
    usable_urls: set[str] | None = None,
) -> LessonOutput:
```

```python
    resources = _parse_resources(
        data.get("resources") or [], concept_ids, usable_urls
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_studio_lessons.py -v`
Expected: PASS（含既有测试）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/lessons.py tests/test_studio_lessons.py
git commit -m "feat: enforce resource roles and real last_verified dates"
```

---

### Task 7: 提示词与 Web 接线（逐查询路由、预检、可用链接）

**Files:**
- Modify: `src/testbridge/studio/prompts.py`
- Modify: `src/testbridge/studio/version.py`
- Modify: `web/studio.py`
- Modify: `web/app.py`
- Test: `tests/test_studio_web.py`、`tests/test_studio_version.py`、`tests/test_studio_routing.py`

**Interfaces:**
- Consumes: Task 4 的 `run_research(..., route_for=)`、`render_research_for_prompt`、`usable_urls_from_payload`；Task 5 的 `check_urls`、`ResourceCheck`。
- Produces:
  - `create_app(..., studio_url_checker=None)`
  - `mount_studio(..., url_checker=None)`；`url_checker: Callable[[list[str]], dict[str, ResourceCheck]]`
  - `PROMPT_VERSION == "studio/3"`

- [ ] **Step 1: Write the failing tests**

`tests/test_studio_version.py`：

```python
    assert PROMPT_VERSION == "studio/3"
```

`tests/test_studio_web.py`：把 `assert entry["prompt_version"] == "studio/2"` 改为 `"studio/3"`；
把 `LESSON_JSON` 的资源改为带显式 kind/role（否则 `provenance.source_mix` 拿不到分，
`test_full_flow_validates_and_promotes` 的 100 分会掉）：

```python
    '"resources": [{"id": "DOC-1", "title": "Executors", '
    '"url": "https://docs.ros.org/x", "type": "official-doc", '
    '"kind": "official_docs", "role": "required", '
    '"trust": "A", "license": "Apache-2.0", '
    '"last_verified": "2026-10-25", "coverage": ["executor-basics"], '
    '"why": "官方"}]}'
```

并新增：

```python
from testbridge.studio.verify import ResourceCheck


def ok_checker(urls):
    return {url: ResourceCheck(url, 200, url, 4000, False, "") for url in urls}


def make_app(tmp_path: Path, *, checker=ok_checker):
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=FakeLlm(),
        studio_search=FakeSearchRouter(),
        studio_config=CONFIG,
        studio_url_checker=checker,
    ))


def test_research_records_check_and_keeps_score(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)

    app.post("/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"})
    dossier = app.app.state.studio_store.read("demo", "research/L-EXEC-001.json")
    assert '"paywalled": false' in dossier
    assert '"kind":' in dossier

    app.post("/api/studio/demo/lessons", json={"lesson_id": "L-EXEC-001"})
    resources = app.app.state.studio_store.read("demo", "resources.yaml")
    assert "last_verified:" in resources
    assert "last_verified: ''" not in resources


def test_paywalled_hit_is_hidden_from_the_model(tmp_path: Path) -> None:
    def walled(urls):
        return {
            url: ResourceCheck(url, 200, url, 4000, True, "") for url in urls
        }

    app = make_app(tmp_path, checker=walled)
    create_draft(app)
    app.post("/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"})
    response = app.post(
        "/api/studio/demo/lessons", json={"lesson_id": "L-EXEC-001"}
    )

    llm = app.app.state.studio_llm
    assert "<research>" in llm.lesson_prompts[-1]
    assert "docs.ros.org/x" not in llm.lesson_prompts[-1]
    assert response.status_code >= 400
```

（`make_app` 现有定义需替换；`app.state.studio_llm` 需要在 `mount_studio` 中保存——见下面实现。若现有 `make_app` 已有 `SAMPLE` 常量，沿用。）

`tests/test_studio_routing.py`：新增逐查询路由拦截：

```python
class KindRouter:
    def __init__(self) -> None:
        self.kinds: list[str] = []

    def route_query(self, backend, kind, **kwargs):
        self.kinds.append(kind)
        return SearchRoute(f"auto:{kind}", FakeSearch())


def test_research_routes_each_query_by_kind(tmp_path: Path) -> None:
    router = KindRouter()
    app = make_app(tmp_path, router)
    create_draft(app, backend="auto")

    app.post("/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"})

    assert "engineering" in router.kinds
    assert "official" in router.kinds
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_studio_version.py tests/test_studio_web.py tests/test_studio_routing.py -v`
Expected: FAIL — `studio/2`，`create_app` 不接受 `studio_url_checker`，`route_query` 未被调用。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/studio/version.py`：

```python
PROMPT_VERSION = "studio/3"
```

`src/testbridge/studio/prompts.py`：`LESSON_SYSTEM` 的资源段（第 6 条）替换为：

```python
    "6. 每课至少 1 条 role=required 的 A/B 资源，并至少尝试 1 条 kind 为 "
    "official_docs / standard / repository 的 required 资源；allowed kind："
    "official_docs/standard/engineering_blog/tutorial/repository/paper/book/video/other。\n"
    "   资源配置：id、title、url、type、kind、role、trust、license、last_verified、"
    "coverage（概念 id 数组）、why；required 的 trust 只能是 A 或 B；"
    "C 级只能作为 role=supplementary（每课 2–3 条工程博客/教程）；D 不可用。"
    "只引用 <research> 中已通过预检的条目，禁止编造 URL；"
    "license / why 不得为空；why 必须写“工程上什么时候用”。\n"
```

`OUTLINE_SYSTEM` 第 4 条改为：

```python
    "4. 每课给出 1–5 条 objectives、1–3 条 exercise_intents、1–3 条 research_queries；"
    "research_queries 必须同时包含工程实践向（best practices / tutorial / 测试方法）"
    "与官方文档向（site:docs.ros.org、site:github.com、厂商文档）查询，"
    "不要全部是论文检索。\n"
```

`web/studio.py`：

1. imports 增加：

```python
from testbridge.studio.research import (
    render_research_for_prompt, usable_urls_from_payload,
)
```

2. `mount_studio` 签名增加 `url_checker=None`：

```python
def mount_studio(
    app,
    templates,
    *,
    drafts_root: Path,
    packs_root: Path,
    config: TutorConfig | None,
    llm: LlmClient | None,
    search: SearchProvider | SearchRouter | None,
    inline: bool = False,
    url_checker=None,
) -> None:
```

3. 路由 helper 增加按查询类型版本：

```python
    def route_for_query(
        draft: dict, titles: list[str], domains: list[str], kind: str
    ) -> SearchRoute:
        backend = str(draft.get("search_backend") or "auto")
        if hasattr(search, "route_query"):
            return search.route_query(
                backend, kind,
                topic=str(draft.get("topic") or ""),
                concept_titles=titles,
                concept_domains=domains,
            )
        return route_for(draft, titles, domains)
```

4. `generate_research` 改为逐查询路由 + 预检：

```python
    def generate_research(draft_id: str, lesson_id: str) -> None:
        draft = store.load(draft_id)
        plan = lesson_plan(draft_id, lesson_id)
        items = concepts(draft_id)
        titles = [str(item.get("title", "")) for item in items]
        domains = [str(item.get("domain", "")) for item in items]

        def progress(done: int, total: int, hits: int) -> None:
            store.set_step(
                draft_id, "research", lesson_id=lesson_id,
                extra={"queries": done, "total": total, "hits": hits},
            )

        result = research_runner.run_research(
            plan, titles,
            budget=draft["searches_per_lesson"],
            progress=progress,
            route_for=lambda kind: route_for_query(draft, titles, domains, kind),
        )
        checks = None
        if url_checker is not None:
            checks = check_urls(url_checker, [hit.url for hit in result.hits])
        research_runner.write_research(
            store, draft_id, plan, result, checks=checks
        )
        add_usage(draft_id, searches=result.searches)
        store.set_step(
            draft_id, "research", lesson_id=lesson_id,
            extra={
                "queries": result.searches,
                "hits": len(result.hits),
                "backend": result.backend,
            },
        )
```

`check_urls` 的第一个参数是 `client`；这里的 `url_checker` 是注入的“批量检查器”，签名 `Callable[[list[str]], dict[str, ResourceCheck]]`。为保持 Task 5 的 `check_urls(client, urls, limit=10)` 不变，web 直接调用注入函数：

```python
        checks = None
        if url_checker is not None:
            checks = url_checker([hit.url for hit in result.hits][:10])
```

5. `research_text` 改为过滤版，同时保留原始读取：

```python
    def research_payload(draft_id: str, lesson_id: str) -> str:
        path = store.path(draft_id) / f"research/{lesson_id}.json"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def research_text(draft_id: str, lesson_id: str) -> str:
        return render_research_for_prompt(research_payload(draft_id, lesson_id))
```

6. `generate_lesson` 使用可用链接：

```python
    def generate_lesson(
        draft_id: str, lesson_id: str, *, replace: bool = False
    ) -> None:
        plan = lesson_plan(draft_id, lesson_id)
        concept_ids = {item["id"] for item in concepts(draft_id)}
        usable = usable_urls_from_payload(research_payload(draft_id, lesson_id))
        output = generate(
            draft_id,
            LESSON_SYSTEM,
            render_lesson_prompt(
                render_lesson_outline(plan),
                concepts_text(draft_id, plan.concepts),
                research_text(draft_id, lesson_id),
            ),
            lambda raw: lesson_writer.parse_lesson_json(
                raw, plan, concept_ids, usable_urls=usable
            ),
        )
        lesson_writer.write_lesson(
            store, draft_id, plan, output, replace=replace, namespace=True
        )
```

7. 在 `mount_studio` 内保存引用供测试与调试：

```python
    app.state.studio_llm = llm
    app.state.studio_search = search
```

`web/app.py`：

1. import `httpx`（文件顶部），并在 `create_app` 签名增加 `studio_url_checker=None`；把该参数传给 `mount_studio`。
2. 在 `mount_studio(...)` 调用前构造默认检查器：

```python
    if studio_url_checker is None and (
        os.environ.get("TESTBRIDGE_STUDIO_VERIFY", "1") != "0"
    ):
        from testbridge.studio.verify import check_url, check_urls

        def studio_url_checker(urls):
            client = httpx.Client(timeout=10.0, follow_redirects=True)
            try:
                return check_urls(client, urls)
            finally:
                client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_studio_version.py tests/test_studio_web.py tests/test_studio_routing.py tests/test_studio_prompts.py -v`
Expected: PASS（`prompt_version` 断言已改为 `studio/3`；调研档案含 `check` / `kind`）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/prompts.py src/testbridge/studio/version.py \
  web/studio.py web/app.py tests/test_studio_version.py tests/test_studio_web.py \
  tests/test_studio_routing.py
git commit -m "feat: wire per-query routing and link preflight into studio"
```

---

### Task 8: 质量门禁按 role 计分并新增来源指标

**Files:**
- Modify: `src/testbridge/quality/provenance.py`
- Test: `tests/test_quality_rules.py` (append)、`tests/test_resource_kind.py` (append)

**Interfaces:**
- Produces:
  - `provenance.MAX_SUPPLEMENTARY_PER_LESSON = 3`
  - 新错误码：`quality.resource_unreachable`、`quality.resource_trust`（复用）
  - 新警告码：`quality.resource_unchecked`、`quality.resource_stale`、`quality.supplementary_too_many`、`quality.lesson_only_papers`、`quality.lesson_no_ab_required`
  - 新指标：`provenance.source_mix`（5 分）、`provenance.reachable`（5 分，无检查记录时不出现）

- [ ] **Step 1: Write the failing tests**

在 `tests/test_quality_rules.py` 追加（复用文件内 `build_pack` / `write_research` helper）：

同时修改既有 fixture 与断言，使新增的 `source_mix`（5 分）有真实输入：

1. `default_resource()` 增加 `"kind": "official_docs", "role": "required"`。
2. `test_clean_pack_scores_100_with_research`：`assert report.possible == 105`。
3. `test_research_without_budget_omits_query_metric`：`assert report.possible == 100`。

```python
def test_supplementary_c_is_allowed_and_not_scored(tmp_path: Path) -> None:
    resources = [
        default_resource(),
        {**default_resource(), "id": "DOC-2", "trust": "C",
         "role": "supplementary", "url": "https://blog.example/x"},
    ]
    pack = build_pack(tmp_path / "pack", resources=resources,
                      lesson_resources=["DOC-1", "DOC-2"])
    research = write_research(tmp_path / "pack", hits=[
        {"url": "https://docs.example/x", "trust": "A"},
        {"url": "https://blog.example/x", "trust": "C"},
    ])

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert not any(
        issue.code == "quality.resource_trust" for issue in result.errors
    )
    trust = next(
        metric for metric in result.metrics if metric.key == "provenance.trust"
    )
    assert trust.detail == "1/1"


（`trust=D` 已在契约层被 `validate_pack` 拒绝（Task 1 的
`test_validator_rejects_d_for_any_role`），`load_pack` 因此到不了质量层；本任务不为
不可达分支补测试。`provenance` 里保留的 D 分支只是防御性代码。）

def test_unreachable_required_is_an_error(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack", hits=[{
        "url": "https://docs.example/x", "trust": "A",
        "check": {"url": "https://docs.example/x", "status": 200,
                  "final_url": "https://docs.example/x",
                  "content_length": 5000, "paywalled": True, "error": ""},
    }])

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(
        issue.code == "quality.resource_unreachable" for issue in result.errors
    )


def test_unchecked_required_is_a_warning(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack")

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(
        issue.code == "quality.resource_unchecked" for issue in result.warnings
    )


def test_supplementary_soft_cap_warning(tmp_path: Path) -> None:
    extra = [
        {**default_resource(), "id": f"DOC-{index}", "trust": "C",
         "role": "supplementary", "url": f"https://blog.example/{index}"}
        for index in range(2, 6)
    ]
    resources = [default_resource(), *extra]
    pack = build_pack(
        tmp_path / "pack", resources=resources,
        lesson_resources=[item["id"] for item in resources],
    )
    research = write_research(tmp_path / "pack", hits=[
        {"url": "https://docs.example/x", "trust": "A"},
        *[{"url": item["url"], "trust": "C"} for item in extra],
    ])

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(
        issue.code == "quality.supplementary_too_many"
        for issue in result.warnings
    )


def test_only_papers_warning_and_source_mix(tmp_path: Path) -> None:
    resources = [{**default_resource(), "kind": "paper"}]
    pack = build_pack(tmp_path / "pack", resources=resources)
    research = write_research(tmp_path / "pack", hits=[{
        "url": "https://docs.example/x", "trust": "A",
        "check": {"url": "https://docs.example/x", "status": 200,
                  "final_url": "https://docs.example/x",
                  "content_length": 5000, "paywalled": False, "error": ""},
    }])

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(
        issue.code == "quality.lesson_only_papers" for issue in result.warnings
    )
    mix = next(
        metric for metric in result.metrics if metric.key == "provenance.source_mix"
    )
    assert mix.earned == 0
    reachable = next(
        metric for metric in result.metrics if metric.key == "provenance.reachable"
    )
    assert reachable.earned == 5


def test_published_pack_has_no_new_metrics(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")

    result = evaluate_provenance(load_pack(pack))

    keys = {metric.key for metric in result.metrics}
    assert "provenance.source_mix" not in keys
    assert "provenance.reachable" not in keys
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_quality_rules.py -v`
Expected: FAIL — supplementary C 仍报错；新错误码/指标不存在。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/quality/provenance.py` 增加常量：

```python
AB_TRUST = {"A", "B"}
ALLOWED_SUPPLEMENTARY_TRUST = {"A", "B", "C"}
MAX_SUPPLEMENTARY_PER_LESSON = 3
STALE_DAYS = 180
OFFICIAL_KINDS = {"official_docs", "standard", "repository"}
PRACTICE_KINDS = {"engineering_blog", "tutorial", "repository"}
```

替换 `evaluate_provenance` 的资源循环与指标段（保持函数签名不变）：

```python
def _days_old(value: str) -> int | None:
    from datetime import date

    try:
        return (date.today() - date.fromisoformat(value)).days
    except ValueError:
        return None


def evaluate_provenance(
    pack: ContentPack,
    research_dir: Path | None = None,
    budget: int | None = None,
    *,
    include_metrics: bool = True,
) -> ProvenanceResult:
    result = ProvenanceResult()
    resources = list(pack.resources.values())
    required = [item for item in resources if item.role == "required"]

    trust_ok = sum(1 for item in required if item.trust in AB_TRUST)
    metadata_ok = sum(
        1
        for item in resources
        if item.license and item.last_verified and item.why
    )
    for resource in resources:
        if resource.trust == "D":
            result.errors.append(_error(
                "quality.resource_trust",
                f"资源 {resource.id} 的 trust 是 D，不可用",
                resource_id=resource.id,
            ))
        elif resource.role == "required" and resource.trust not in AB_TRUST:
            result.errors.append(_error(
                "quality.resource_trust",
                f"资源 {resource.id} 的 trust 是 {resource.trust}，只允许 A/B",
                resource_id=resource.id,
            ))
        if not (resource.license and resource.why):
            result.warnings.append(_warning(
                "quality.resource_metadata",
                f"资源 {resource.id} 缺少 license / last_verified / why",
                resource_id=resource.id,
            ))
        elif not resource.last_verified:
            result.warnings.append(_warning(
                "quality.resource_metadata",
                f"资源 {resource.id} 缺少 license / last_verified / why",
                resource_id=resource.id,
            ))
        elif (_days_old(resource.last_verified) or 0) > STALE_DAYS:
            result.warnings.append(_warning(
                "quality.resource_stale",
                f"资源 {resource.id} 的验证日期超过 {STALE_DAYS} 天",
                resource_id=resource.id,
            ))
```

（保留原 `resource_metadata` 的合并消息，避免既有测试断言变更；补充 `resource_stale`。）

`include_metrics` 段：

```python
    if include_metrics:
        result.metrics.append(QualityMetric(
            "provenance.trust", "资源可信",
            proportional(trust_ok, len(required), 10), 10,
            f"{trust_ok}/{len(required)}",
        ))
        result.metrics.append(QualityMetric(
            "provenance.metadata", "资源元数据完整",
            proportional(metadata_ok, len(resources), 5), 5,
            f"{metadata_ok}/{len(resources)}",
        ))
```

`research_dir` 分支内，追溯段改为按 role：

```python
    traceable = 0
    for resource in resources:
        normalized = normalize_url(resource.url)
        if resource.role == "supplementary":
            if normalized and normalized in all_urls:
                traceable += 1
            else:
                result.errors.append(_error(
                    "quality.resource_unsourced",
                    f"资源 {resource.id} 的 URL 不在任何调研档案中",
                    resource_id=resource.id,
                ))
            continue
        if normalized and normalized in ab_urls:
            traceable += 1
        elif normalized and normalized in all_urls:
            result.errors.append(_error(
                "quality.resource_untrusted_source",
                f"资源 {resource.id} 的来源命中不是 A/B",
                resource_id=resource.id,
            ))
        else:
            result.errors.append(_error(
                "quality.resource_unsourced",
                f"资源 {resource.id} 的 URL 不在任何调研档案中",
                resource_id=resource.id,
            ))
```

在 `ab_urls` 计算之后加入检查记录索引：

```python
    checks_by_url: dict[str, dict] = {}
    for dossier in dossiers.values():
        for hit in dossier.hits:
            check = hit.get("check")
            if isinstance(check, dict):
                checks_by_url[normalize_url(str(hit.get("url") or ""))] = check
    checked_required = 0
    reachable_ok = 0
    for resource in required:
        check = checks_by_url.get(normalize_url(resource.url))
        if check is None:
            result.warnings.append(_warning(
                "quality.resource_unchecked",
                f"资源 {resource.id} 没有可达性检查记录",
                resource_id=resource.id,
            ))
            continue
        checked_required += 1
        status = check.get("status")
        if (
            check.get("paywalled")
            or check.get("error")
            or not isinstance(status, int)
            or status >= 400
        ):
            result.errors.append(_error(
                "quality.resource_unreachable",
                f"资源 {resource.id} 不可达或处于付费墙内",
                resource_id=resource.id,
            ))
        else:
            reachable_ok += 1
```

在 `provenance.traceable` 指标之后加入新指标：

```python
    mix_ok = 0
    for lesson in pack.lessons_in_order():
        manifest = lesson.manifest
        lesson_resources = [
            pack.resources[item] for item in manifest.resources
            if item in pack.resources
        ]
        lesson_required = [
            item for item in lesson_resources if item.role == "required"
        ]
        if not lesson_required:
            result.warnings.append(_warning(
                "quality.lesson_no_ab_required",
                f"{manifest.id} 没有 A/B required 资源",
                lesson_id=manifest.id,
            ))
        elif all(item.kind == "paper" for item in lesson_required):
            result.warnings.append(_warning(
                "quality.lesson_only_papers",
                f"{manifest.id} 的 required 资源全是论文",
                lesson_id=manifest.id,
            ))
        if any(
            item.kind in OFFICIAL_KINDS | PRACTICE_KINDS
            for item in lesson_required
        ):
            mix_ok += 1
        supplementary = [
            item for item in lesson_resources if item.role == "supplementary"
        ]
        if len(supplementary) > MAX_SUPPLEMENTARY_PER_LESSON:
            result.warnings.append(_warning(
                "quality.supplementary_too_many",
                f"{manifest.id} 有 {len(supplementary)} 条补充阅读，"
                f"建议不超过 {MAX_SUPPLEMENTARY_PER_LESSON}",
                lesson_id=manifest.id,
            ))
    result.metrics.append(QualityMetric(
        "provenance.source_mix", "来源配比",
        proportional(mix_ok, len(lessons), 5), 5,
        f"{mix_ok}/{len(lessons)}",
    ))
    if checked_required:
        result.metrics.append(QualityMetric(
            "provenance.reachable", "required 可达",
            proportional(reachable_ok, checked_required, 5), 5,
            f"{reachable_ok}/{checked_required}",
        ))
```

注意：`lessons` 变量已在原函数后半段定义为 `pack.lessons_in_order()`，把新代码放在该定义之后（原“dossier 可用”循环之前或之后均可，保证 `lessons` 已绑定）。

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_quality_rules.py tests/test_quality_report.py tests/test_resource_kind.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/quality/provenance.py tests/test_quality_rules.py
git commit -m "feat: score required and supplementary resources separately"
```

---

### Task 9: 文档与全量验收

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/OPTIMIZATION.md`
- Modify: `docs/superpowers/specs/2026-10-26-o3-resource-quality-design.md`
- Modify: `README.md`

- [ ] **Step 1: Update the spec status**

把 spec 头部改为：

```markdown
- 状态：Implemented，2026-10-26
```

- [ ] **Step 2: Update ROADMAP**

1. 在“优化清单”表格下方一段的进度句中加入 O3 完成说明与验证命令。
2. 更新“排期建议”句为：O1、O3 已完成；下一步 O2。
3. 新增一节：

```markdown
## O3 参考资料工程化（已完成，2026-10-26）

**范围：**

- 资源新增可选 `kind` / `role`；`required` 只允许 A/B，`supplementary` 允许 A/B/C，D 一律拒绝。
- `auto` 按查询类型分流：学术走 OpenAlex，工程/官方走 DeepSeek；手动后端不回退。
- OpenAlex 优先给 OA 链接，其次 landing page，最后 DOI。
- 调研阶段预检前 10 条命中：状态码、最终 URL、正文长度、付费墙启发式；
  档案记录 `kind` / `trust` / `check` 与逐查询 `backend`。
- 写课只看到通过预检的命中；`required` 未通过预检直接拒绝。
- `last_verified` 只在检查通过时写当天，不再自动填今天。
- `tb verify-resources <pack>`：显式联网复查，required 失败返回 1。
- 质量门禁：`provenance.trust` 只统计 required；新增 `source_mix`（5 分）与
  `reachable`（5 分，仅在有检查记录时出现）；新增
  `resource_unreachable` / `resource_unchecked` / `resource_stale` /
  `supplementary_too_many` / `lesson_only_papers` / `lesson_no_ab_required`。
- prompt 版本 `studio/3`；旧草稿继续按 `studio/1` / `studio/2` 显示，不自动迁移。

**不做：** 付费墙绕过、C 级自动升 B、SearXNG / Firecrawl / arXiv 适配器、
外部图片与 AI 生图（属 O2）。

**验证命令（2026-10-26）：**

```text
$ .venv/Scripts/python -m pytest -q
<paste actual output>

$ .venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli quality content-packs/sample-sensors
quality: 100/100                # exit 0
```
```

（测试数字与输出在执行时填入真实值，不要照抄占位符。）

- [ ] **Step 3: Update OPTIMIZATION**

§0.2 的“进度”改为：

```markdown
**进度：** O1 已实现（2026-10-26）；O3 已实现（2026-10-26，分支 `p5-optimization`）。
O3 完成时默认 `pytest` <填入实际数字>、3 deselected；两个现有包 `tb validate` 0/0，
`tb quality content-packs/sample-sensors` 100/100。下一步 O2。
```

- [ ] **Step 4: Update README**

在“一次性配置模型（Windows）”之后加一段：

```markdown
## 复查资源链接（可选，联网）

```bash
.venv/Scripts/python -m testbridge.cli verify-resources content-packs/<pack>
```

required 资源的死链或付费墙会返回退出码 1；补充阅读失败只提示，不阻断。
Studio 调研时默认会预检前 10 条命中；如需完全离线，设置
`TESTBRIDGE_STUDIO_VERIFY=0`。
```

- [ ] **Step 5: Run the full verification**

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
.venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
.venv/Scripts/python -m testbridge.cli quality content-packs/sample-sensors
.venv/Scripts/python -m testbridge.cli quality content-packs/robot-quality-system
```

Expected: pytest 全绿（3 deselected）；两个包 `0 error(s), 0 warning(s)`；
`sample-sensors` 仍 100/100；`robot-quality-system` 分数不低于改动前
（改动前记录一次基线对照）。

- [ ] **Step 6: Commit**

```bash
git add docs/ROADMAP.md docs/OPTIMIZATION.md README.md \
  docs/superpowers/specs/2026-10-26-o3-resource-quality-design.md
git commit -m "docs: record O3 completion"
```

---

## Self-Review

**Spec coverage:**

| Spec 章节 | 任务 |
|---|---|
| §3 契约扩展与兼容映射 | Task 1 |
| §4.1 查询带类型 | Task 4 |
| §4.2 按查询路由 | Task 4 |
| §4.3 来源分类与白名单 | Task 2 |
| §4.4 OpenAlex URL 选择 | Task 3 |
| §5 可达性检查（预检/写课/定稿/事后） | Task 5、6、7 |
| §6 质量门禁与指标 | Task 8 |
| §7 提示词与 `studio/3` | Task 7 |
| §8 兼容与边界 | Task 1、5、7 |
| §9 测试矩阵 | 各任务测试 + Task 9 回归 |

**已知取舍：**

- 调研预检默认开启、由 `TESTBRIDGE_STUDIO_VERIFY=0` 关闭；测试注入
  `studio_url_checker`，默认 `pytest` 不联网。
- `provenance.reachable` 只在至少一条 required 有检查记录时出现，避免无预检的
  草稿被无意义扣分；已发布包没有调研目录，因此不出现。
- 旧草稿资源缺 `role` 时按 `required` 处理（Pydantic 默认值），与 spec §3 一致。
- `last_verified` 被清空会让无预检草稿的 `provenance.metadata` 下降；这是
  真实信号，不为了分数回填空日期。
