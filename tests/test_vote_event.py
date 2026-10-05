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
    # 1. 존재하는 이벤트 bazaarposter
    response = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
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


def test_unauthenticated_admin_create_redirects_to_keycloak():
    """비로그인 사용자가 새 이벤트 개설 페이지 접근 시 Keycloak 로그인으로 303 리다이렉트 검증"""
    res = client.get(f"{DEFAULT_PREFIX}/create", follow_redirects=False)
    assert res.status_code == 303
    location = res.headers.get("location", "")
    assert "holyseeds.thewayworks.net/auth/login" in location
    assert "require_role=manager" in location
    assert "redirect=" in location


def test_unauthenticated_admin_edit_and_delete_redirects_to_keycloak():
    """비로그인 사용자가 이벤트 수정 및 삭제 액션 시도 시 303 리다이렉트 검증"""
    # 1. 수정 폼 페이지 접근
    edit_res = client.get(f"{DEFAULT_PREFIX}/edit/1", follow_redirects=False)
    assert edit_res.status_code == 303
    assert "require_role=manager" in edit_res.headers.get("location", "")

    # 2. 삭제 액션 요청
    del_res = client.post(f"{DEFAULT_PREFIX}/delete/1", follow_redirects=False)
    assert del_res.status_code == 303
    assert "require_role=manager" in del_res.headers.get("location", "")


from unittest.mock import patch, MagicMock

def test_manager_authorized_admin_actions():
    """manager flag=1 인증 세션이 있을 때 이벤트 개설 및 수정 정상 수행 검증"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "valid": True,
        "is_manager": True,
        "role_flag": "1",
        "roles": ["manager"],
        "user": {"name": "홍길동", "username": "01012345678"}
    }

    with patch("app.core.auth.requests.get", return_value=mock_resp):
        # 쿠키 auth_session 포함 요청
        client.cookies.set("auth_session", "valid_manager_session_token")

        # 1. 새 이벤트 개설 화면 접근 (200 OK)
        create_page = client.get(f"{DEFAULT_PREFIX}/create")
        assert create_page.status_code == 200
        assert "이벤트 기본 정보" in create_page.text

        import uuid
        test_slug = f"authtest_{uuid.uuid4().hex[:8]}"

        # 2. 새 이벤트 등록 (POST)
        post_res = client.post(
            f"{DEFAULT_PREFIX}/create",
            data={
                "slug": test_slug,
                "title": "인증 테스트 이벤트",
                "description": "매니저 권한으로 생성된 이벤트입니다."
            },
            follow_redirects=False
        )
        assert post_res.status_code == 303
        assert post_res.headers["location"] == f"{DEFAULT_PREFIX}/"

        # 3. 목록 화면에서 사용자 이름 확인
        list_res = client.get(f"{DEFAULT_PREFIX}/")
        assert list_res.status_code == 200
        assert "홍길동" in list_res.text
        assert "Manager" in list_res.text

        # 쿠키 정리
        client.cookies.clear()
