import warnings
from datetime import date, timedelta
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

ROOT = Path(__file__).parents[1]
SAMPLE = ROOT / "content-packs" / "sample-sensors"


def make_app(tmp_path: Path) -> TestClient:
    return TestClient(create_app(SAMPLE, tmp_path / "apps.db"))


def today(offset: int = 0) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def create_data(**overrides) -> dict:
    data = {
        "company": "某机器人公司",
        "role": "测试工程师",
        "source": "内推",
        "status": "applied",
        "applied_at": today(),
        "next_action": "补发简历",
        "next_action_at": today(1),
        "notes": "HR 说一周内回复",
    }
    data.update(overrides)
    return data


def test_empty_list_and_form(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.get("/applications")
    assert response.status_code == 200
    assert "还没有投递记录" in response.text
    assert 'name="company"' in response.text


def test_nav_shows_applications(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    assert 'href="/applications"' in c.get("/").text


def test_create_redirects_and_lists(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.post("/applications", data=create_data(),
                      follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/applications/")
    page = c.get("/applications").text
    assert "某机器人公司" in page
    assert "测试工程师" in page


def test_create_validation_preserves_input(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.post("/applications", data=create_data(company=""))
    assert response.status_code == 400
    assert "公司不能为空" in response.text
    assert "测试工程师" in response.text


def test_status_filter(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    c.post("/applications", data=create_data(status="applied"))
    c.post("/applications", data=create_data(company="另一家", status="offer"))
    page = c.get("/applications?status=offer").text
    assert "另一家" in page
    assert "某机器人公司" not in page


def create_one(c: TestClient, **overrides) -> str:
    response = c.post("/applications", data=create_data(**overrides),
                      follow_redirects=False)
    return response.headers["location"].rsplit("/", 1)[-1]


def test_detail_renders_and_escapes(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    app_id = create_one(c, company="<b>公司</b>", notes="<script>x</script>")
    page = c.get(f"/applications/{app_id}").text
    assert "&lt;b&gt;公司&lt;/b&gt;" in page
    assert "<b>公司</b>" not in page
    assert "&lt;script&gt;" in page


def test_unknown_detail_is_404(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    assert c.get("/applications/nope").status_code == 404


def test_update_status_and_notes(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    app_id = create_one(c)
    response = c.post(f"/applications/{app_id}", data=create_data(
        status="interviewing", notes="约了下周"),
        follow_redirects=False)
    assert response.status_code == 303
    page = c.get(f"/applications/{app_id}").text
    assert "interviewing" in page
    assert "约了下周" in page


def test_update_validation_preserves_input(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    app_id = create_one(c)
    response = c.post(f"/applications/{app_id}", data=create_data(
        applied_at="2026/10/26", notes="保留我"),
    )
    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.text
    assert "保留我" in response.text


def test_withdraw(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    app_id = create_one(c)
    response = c.post(f"/applications/{app_id}/withdraw",
                      follow_redirects=False)
    assert response.status_code == 303
    page = c.get(f"/applications/{app_id}").text
    assert "withdrawn" in page


def test_list_escapes_company(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    create_one(c, company="<script>公司</script>")
    page = c.get("/applications").text
    assert "&lt;script&gt;公司&lt;/script&gt;" in page
    assert "<script>公司</script>" not in page
