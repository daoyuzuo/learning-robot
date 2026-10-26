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
