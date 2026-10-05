import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import DEFAULT_PREFIX, UPLOAD_DIR
from app.core.database import init_db

client = TestClient(app)


def make_test_image(width: int = 2100, height: int = 1500) -> bytes:
    """테스트용 이미지 바이너리 생성 (기본 폭 2100px: 1920px 초과)"""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_root_redirect():
    """루트 경로 접속 시 DEFAULT_PREFIX(/votes/)로 302 리다이렉트 검증"""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == f"{DEFAULT_PREFIX}/"


def test_health_check_status():
    """컨테이너 헬스체크 엔드포인트({DEFAULT_PREFIX}/api/status 및 /api/status) 검증"""
    # 1. Prefix 경로 헬스체크
    response = client.get(f"{DEFAULT_PREFIX}/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["prefix"] == DEFAULT_PREFIX
    assert data["database"] == "connected"

    # 2. 루트 /api/status 헬스체크
    root_response = client.get("/api/status")
    assert root_response.status_code == 200
    assert root_response.json()["status"] == "ok"


def test_admin_event_list():
    """관리자 이벤트 목록 페이지 접속 검증"""
    response = client.get(f"{DEFAULT_PREFIX}/")
    assert response.status_code == 200
    assert "이벤트 관리 대시보드" in response.text


def test_event_public_landing_and_not_found():
    """이벤트 Subpath 랜딩 및 존재하지 않는 이벤트 404 페이지 검증"""
    # 1. 존재하는 이벤트 baazarposter
    response = client.get(f"{DEFAULT_PREFIX}/baazarposter")
    assert response.status_code == 200
    assert "바자회 홍보 포스터 자랑대회" in response.text

    # 2. 존재하지 않는 이벤트
    response_404 = client.get(f"{DEFAULT_PREFIX}/unknown_event_slug_12345")
    assert response_404.status_code == 404
    assert "이벤트를 찾을 수 없습니다" in response_404.text


def test_item_create_resize_and_workflow():
    """참여 항목 생성, 1920px 리사이즈, 투표, PIN 수정 및 삭제 E2E 워크플로우 검증"""
    # 1. 2100px 대형 이미지 업로드 항목 등록
    large_image = make_test_image(2100, 1500)
    files = {
        "image": ("test_poster_large.jpg", io.BytesIO(large_image), "image/jpeg")
    }
    data = {
        "event_id": 1,
        "title": "테스트 자동화 포스터",
        "description": "pytest에서 업로드한 2100px 대형 포스터입니다.",
        "pin": "7777"
    }

    create_res = client.post(f"{DEFAULT_PREFIX}/api/items", data=data, files=files)
    assert create_res.status_code == 200
    item_json = create_res.json()
    item_id = item_json["id"]
    assert item_json["title"] == "테스트 자동화 포스터"

    # 2. 저장된 파일의 해상도가 가로 폭 1920px 이하로 변환되었는지 디스크 파일 검증
    saved_rel_path = item_json["image_path"]
    saved_full_path = UPLOAD_DIR / saved_rel_path
    assert saved_full_path.exists()

    with Image.open(saved_full_path) as saved_img:
        w, h = saved_img.size
        assert w == 1920, f"저장된 이미지 폭은 1920px이어야 합니다! (실제: {w})"

    # 3. 투표 테스트
    vote_res = client.post(f"{DEFAULT_PREFIX}/api/items/{item_id}/vote")
    assert vote_res.status_code == 200
    assert vote_res.json()["success"] is True
    assert vote_res.json()["vote_count"] == 1

    # 4. PIN 오입력 수정 시도 -> 403 거부
    bad_edit_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/{item_id}/update",
        data={"pin": "wrong_pin", "title": "수정 시도"}
    )
    assert bad_edit_res.status_code == 403

    # 5. 올바른 PIN으로 수정 -> 성공
    good_edit_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/{item_id}/update",
        data={"pin": "7777", "title": "수정 완료된 포스터 제목"}
    )
    assert good_edit_res.status_code == 200
    assert good_edit_res.json()["title"] == "수정 완료된 포스터 제목"

    # 6. 올바른 PIN으로 삭제
    delete_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/{item_id}/delete",
        json={"pin": "7777"}
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["success"] is True

    # 파일이 삭제되었는지 확인
    assert not saved_full_path.exists()
