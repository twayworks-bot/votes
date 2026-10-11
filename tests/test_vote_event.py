import io
import uuid
from unittest.mock import patch, MagicMock
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


def test_subpath_login_and_create_links_preserve_auth_prefix():
    """
    /votes/{eventName} 등 서브패스 접근 시 '관리자 로그인' 및 '새 이벤트 개설' 링크에서
    /auth prefix가 유실되지 않고 올바른 Keycloak 로그인 경로를 가리키는지 검증
    """
    from app.core.config import AUTH_URL

    response = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
    assert response.status_code == 200

    html = response.text
    # 1. 관리자 로그인 링크에 /auth/login (AUTH_URL) 포함 여부
    assert "관리자 로그인" in html
    assert f"{AUTH_URL}/login" in html or "/auth/login" in html

    # 2. 새 이벤트 개설 링크에 /auth/login 및 require_role=manager 포함 여부
    assert "새 이벤트 개설" in html
    assert "require_role=manager" in html

    # 3. /auth가 누락된 채 '/login?'으로 링크되는 오류 패턴이 없는지 확인
    assert 'href="/login?' not in html
    assert 'href="/login"' not in html


def test_item_create_resize_and_workflow():
    """참여 항목 생성, 1920px 리사이즈, 투표, PIN 수정 및 삭제 E2E 워크플로우 검증"""
    from app.core.database import SessionLocal
    from app.services import event_service
    db = SessionLocal()
    try:
        ev = event_service.get_event_by_slug(db, "bazaarposter")
        if not ev:
            ev = event_service.create_event(db, slug="bazaarposter", title="바자회 홍보 포스터 자랑대회")
        target_event_id = ev.id
    finally:
        db.close()

    # 1. 2100px 대형 이미지 업로드 항목 등록
    large_image = make_test_image(2100, 1500)
    files = {
        "image": ("test_poster_large.jpg", io.BytesIO(large_image), "image/jpeg")
    }
    data = {
        "event_id": target_event_id,
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


def test_ended_event_behavior():
    """
    이벤트 종료(is_active=False) 시:
    1. UI에서 참여 생성 버튼 및 선호도 투표 버튼이 disabled 처리되는지 검증
    2. 백엔드에서 신규 항목 생성 시 400 차단되는지 검증
    3. 백엔드에서 선호도 투표 시 success=False 및 마감 메시지로 차단되는지 검증
    """
    import uuid
    from app.core.database import SessionLocal
    from app.services import event_service, item_service

    db = SessionLocal()
    ended_slug = f"ended_{uuid.uuid4().hex[:8]}"
    try:
        # 1. 활성 이벤트 생성 후 항목 하나 추가
        ev = event_service.create_event(
            db=db,
            slug=ended_slug,
            title="종료 테스트 이벤트",
            description="이벤트 종료 테스트 설명입니다."
        )
        item = item_service.create_item(
            db=db,
            event_id=ev.id,
            title="종료 전 등록 항목",
            description="테스트 항목",
            pin="1234",
            image_path="items/test.webp"
        )
        item_id = item.id

        # 2. 이벤트를 종료(is_active=False) 상태로 전환
        event_service.update_event(db=db, event_id=ev.id, is_active=False)
        db.refresh(ev)
        assert ev.is_active is False
    finally:
        db.close()

    # 3. UI 렌더링 검증
    page_res = client.get(f"{DEFAULT_PREFIX}/{ended_slug}")
    assert page_res.status_code == 200
    html = page_res.text

    # 상태 뱃지 및 종료 배너
    assert "투표 종료됨" in html
    assert "참여 마감됨" in html
    assert "투표 마감" in html
    assert "수정하기" in html
    assert "삭제하기" in html
    assert "isEventActive = false" in html

    # 4. 백엔드: 종료된 이벤트에 신규 항목 생성 시도 -> 400 에러
    large_image = make_test_image(800, 600)
    files = {
        "image": ("test_poster.jpg", io.BytesIO(large_image), "image/jpeg")
    }
    data = {
        "event_id": ev.id,
        "title": "종료 후 등록 시도 항목",
        "description": "등록되면 안 됩니다.",
        "pin": "7777"
    }
    create_res = client.post(f"{DEFAULT_PREFIX}/api/items", data=data, files=files)
    assert create_res.status_code == 400
    assert "종료된 이벤트" in create_res.json()["detail"]

    # 5. 백엔드: 종료된 이벤트의 기존 항목 수정 시도 -> 400 에러
    update_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/{item_id}/update",
        data={"pin": "1234", "title": "수정 시도 제목"}
    )
    assert update_res.status_code == 400
    assert "종료된 이벤트의 항목은 수정할 수 없습니다" in update_res.json()["detail"]

    # 6. 백엔드: 종료된 이벤트의 기존 항목 삭제 시도 -> 400 에러
    delete_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/{item_id}/delete",
        json={"pin": "1234"}
    )
    assert delete_res.status_code == 400
    assert "종료된 이벤트의 항목은 삭제할 수 없습니다" in delete_res.json()["detail"]

    # 7. 백엔드: 종료된 이벤트의 기존 항목에 투표 시도 -> 실패 및 카운트 미증가
    vote_res = client.post(f"{DEFAULT_PREFIX}/api/items/{item_id}/vote")
    assert vote_res.status_code == 200
    vote_data = vote_res.json()
    assert vote_data["success"] is False
    assert "종료" in vote_data["message"] or "마감" in vote_data["message"]
    assert vote_data["vote_count"] == 0


@pytest.mark.asyncio
async def test_verify_admin_session_function():
    """다른 서비스와 동일한 규격의 verify_admin_session 비동기 검증 함수 단위 테스트"""
    from app.core.auth import verify_admin_session

    # 1. 빈 세션 전달 시 즉시 False 반환
    assert await verify_admin_session("") is False
    assert await verify_admin_session(None) is False

    # 2. Keycloak 정상 관리자 세션 응답 모킹
    mock_mgr_resp = MagicMock()
    mock_mgr_resp.status_code = 200
    mock_mgr_resp.json.return_value = {"valid": True, "is_manager": True}

    with patch("httpx.AsyncClient.get", return_value=mock_mgr_resp):
        assert await verify_admin_session("valid_session_123") is True

    # 3. 일반 사용자 세션 응답 모킹
    mock_user_resp = MagicMock()
    mock_user_resp.status_code = 200
    mock_user_resp.json.return_value = {"valid": True, "is_manager": False}

    with patch("httpx.AsyncClient.get", return_value=mock_user_resp):
        assert await verify_admin_session("normal_user_session") is False


def test_auth_status_endpoint_and_local_login_persistence():
    """
    1. /api/auth/status 엔드포인트 동작 검증
    2. 로컬 로그인 쿼리 파라미터(?session_id=...) 전달 시 브라우저 쿠키(auth_session) 자동 보존 검증
    """
    # 1. 비로그인 상태 auth status
    client.cookies.clear()
    status_res = client.get(f"{DEFAULT_PREFIX}/api/auth/status")
    assert status_res.status_code == 200
    assert status_res.json()["is_manager"] is False

    # 2. 로컬 리다이렉트 케이스: 쿼리스트링 session_id 전달 시 Set-Cookie 확인
    local_login_res = client.get(
        f"{DEFAULT_PREFIX}/",
        params={"session_id": "test_local_session_9999"}
    )
    assert local_login_res.status_code == 200
    # 쿠키에 auth_session이 저장되었는지 확인
    assert "auth_session" in local_login_res.cookies
    assert local_login_res.cookies["auth_session"] == "test_local_session_9999"

    # 쿠키 정리
    client.cookies.clear()


def test_manager_only_access_control_and_ui_tag():
    """
    1. manager_only 활성화 이벤트 생성
    2. 일반/익명 사용자 접속 시 403 차단 및 안내 메시지 확인
    3. 관리자 목록 페이지의 이벤트 카드에 '관리자만 접근' 태그/아이콘 노출 확인
    4. 관리자 로그인 시 200 정상 접속 확인
    5. 비관리자의 API 등록/투표 시 차단 확인
    """
    from app.core.database import SessionLocal
    from app.services import event_service, item_service

    db = SessionLocal()
    mgr_slug = f"mgr_only_{uuid.uuid4().hex[:8]}"
    try:
        ev = event_service.create_event(
            db=db,
            slug=mgr_slug,
            title="관리자 전용 비공개 이벤트",
            description="관리자만 접근할 수 있는 이벤트입니다.",
            manager_only=True,
            hide_vote_counts=False
        )
        event_id = ev.id
        item = item_service.create_item(
            db=db,
            event_id=event_id,
            title="관리자 전용 테스트 작품",
            description="테스트 작품 설명",
            pin="1234",
            image_path="items/mgr_test.webp"
        )
        item_id = item.id
    finally:
        db.close()

    # 1. 익명 사용자 접근 시 403 차단 및 안내 문구 검증
    client.cookies.clear()
    denied_res = client.get(f"{DEFAULT_PREFIX}/{mgr_slug}")
    assert denied_res.status_code == 403
    assert "관리자만 접근이 가능한 이벤트입니다" in denied_res.text
    assert "일반 사용자나 익명사용자는 접근이 허용되지 않습니다" in denied_res.text
    assert "관리자 로그인하기" in denied_res.text

    # 2. 관리자 목록 페이지에 '관리자만 접근' 태그 및 방패 아이콘 노출 검증
    list_res = client.get(f"{DEFAULT_PREFIX}/")
    assert list_res.status_code == 200
    assert "관리자만 접근" in list_res.text
    assert "fa-shield-halved" in list_res.text

    # 3. 비관리자의 API 접근 차단 검증
    # 3-1. 항목 상세 조회 API (/api/items/{id}) -> 403 차단
    item_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item_id}")
    assert item_res.status_code == 403
    assert "관리자 전용 이벤트" in item_res.json()["detail"]

    # 3-2. 신규 항목 등록 API -> 403 차단
    create_res = client.post(
        f"{DEFAULT_PREFIX}/api/items",
        data={"event_id": event_id, "title": "무단 등록 시도", "pin": "1234"},
        files={"image": ("test.jpg", io.BytesIO(b"image_bytes"), "image/jpeg")}
    )
    assert create_res.status_code == 403
    assert "관리자 전용 이벤트" in create_res.json()["detail"]

    # 3-3. 투표 API -> 실패 메시지 반환
    vote_res = client.post(f"{DEFAULT_PREFIX}/api/items/{item_id}/vote")
    assert vote_res.status_code == 200
    vote_json = vote_res.json()
    assert vote_json["success"] is False
    assert "관리자 전용 이벤트" in vote_json["message"]

    # 4. 관리자 로그인(is_manager=True) 모킹 시 정상 접속 (200)
    mock_admin_auth = {
        "valid": True,
        "is_manager": True,
        "user": {"username": "admin_user", "email": "admin@example.com"},
        "authenticated": True
    }
    with patch("app.routers.event_view_router.verify_auth_session", return_value=mock_admin_auth):
        allowed_res = client.get(f"{DEFAULT_PREFIX}/{mgr_slug}")
        assert allowed_res.status_code == 200
        assert "관리자 전용 비공개 이벤트" in allowed_res.text
        assert "참여 작품 갤러리" in allowed_res.text


def test_hide_vote_counts_feature():
    """
    1. hide_vote_counts 활성화 이벤트 생성
    2. 일반 사용자 조회 시:
       - 헤더 총 득표수가 '비공개'로 표시
       - 개별 카드의 득표수 뱃지가 노출되지 않음
       - 모아보기 및 JS rawItems에서 득표수가 0으로 마스킹
       - 인기 투표순 정렬 옵션 미노출
    3. 일반 사용자 투표 시:
       - 투표는 정상 반영되나 반환되는 vote_count가 0으로 마스킹
       - 항목 상세 API에서도 vote_count가 0으로 마스킹
    4. 관리자 조회 시:
       - 헤더 및 카드에 실제 득표수 정상 표시
    """
    from app.core.database import SessionLocal
    from app.services import event_service, item_service

    db = SessionLocal()
    hide_slug = f"hide_votes_{uuid.uuid4().hex[:8]}"
    try:
        ev = event_service.create_event(
            db=db,
            slug=hide_slug,
            title="득표수 비공개 투표 이벤트",
            description="득표수가 숨겨진 이벤트입니다.",
            manager_only=False,
            hide_vote_counts=True
        )
        item = item_service.create_item(
            db=db,
            event_id=ev.id,
            title="득표수 숨김 작품 1",
            description="작품 설명",
            pin="1234",
            image_path="items/hide_test.webp"
        )
        item_id = item.id
    finally:
        db.close()

    # 1. 투표 1표 사전 행사
    client.cookies.clear()
    vote_res = client.post(f"{DEFAULT_PREFIX}/api/items/{item_id}/vote")
    assert vote_res.status_code == 200
    vote_data = vote_res.json()
    assert vote_data["success"] is True
    # 일반 사용자에게는 vote_count가 0으로 마스킹되어 반환
    assert vote_data["vote_count"] == 0

    # 2. 일반 사용자 GET /votes/{slug} 화면 검증
    user_page = client.get(f"{DEFAULT_PREFIX}/{hide_slug}")
    assert user_page.status_code == 200
    user_html = user_page.text

    # 헤더 총 득표수가 '비공개'로 표시됨
    assert 'id="header-total-votes">비공개</span>' in user_html
    # 카드 투표수 뱃지(card-votes-{id})가 미노출
    assert f'id="card-votes-{item_id}"' not in user_html
    # 인기 투표순 버튼 미노출
    assert "인기 투표순" not in user_html
    # JS 플래그 확인
    assert "hideVoteCounts = true" in user_html

    # 3. 항목 조회 API에서도 vote_count 마스킹 검증
    get_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item_id}")
    assert get_res.status_code == 200
    assert get_res.json()["vote_count"] == 0

    # 4. 관리자 로그인 시 실제 득표수 확인 가능 검증
    mock_admin_auth = {
        "valid": True,
        "is_manager": True,
        "user": {"username": "admin_user", "email": "admin@example.com"},
        "authenticated": True
    }
    with patch("app.routers.event_view_router.verify_auth_session", return_value=mock_admin_auth):
        admin_page = client.get(f"{DEFAULT_PREFIX}/{hide_slug}")
        assert admin_page.status_code == 200
        admin_html = admin_page.text
        # 관리자는 총 득표수 1표 확인 가능
        assert 'id="header-total-votes">1표</span>' in admin_html
        # 관리자는 카드 투표수 뱃지 확인 가능
        assert f'id="card-votes-{item_id}">1</span>' in admin_html
        # 관리자는 인기 투표순 정렬 옵션 사용 가능
        assert "인기 투표순" in admin_html

    with patch("app.routers.item_router.verify_auth_session", return_value=mock_admin_auth):
        admin_get_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item_id}")
        assert admin_get_res.status_code == 200
        assert admin_get_res.json()["vote_count"] == 1


def test_client_pre_verification_and_manager_action_redirect_flow():
    """
    1. '새 이벤트 개설', '수정', '삭제' 호출 버튼에 사전 검증 절차(handleManagerAction) 적용 확인
    2. handleManagerAction 스크립트에 내부 시스템 /api/auth/status 사전 검증 로직 포함 확인
    3. 사전 검증 성공 시 Keycloak 리다이렉트 없이 즉시 targetPath 이동하는 로직 확인
    4. 미인증 시 window.location.origin을 포함한 완전한 redirection URL로 이동하여
       local 환경에서도 localhost 복귀 가능한 구조인지 검증
    """
    res = client.get(f"{DEFAULT_PREFIX}/")
    assert res.status_code == 200
    html = res.text

    # 1. 스크립트 정의 검증
    assert "handleManagerAction(event, targetPath, onSuccessCallback)" in html
    assert "/api/auth/status" in html
    assert ("localData.is_manager || localData.is_admin" in html or "authResult.is_manager" in html)
    assert "window.location.origin" in html
    assert "require_role=manager" in html

    # 2. '새 이벤트 개설하기' 버튼에 handleManagerAction 연동 검증
    assert "handleManagerAction(event, '/votes/create')" in html

    # 3. '수정' 및 '삭제' 버튼에 handleManagerAction 연동 검증
    assert "handleManagerAction(event, '/votes/edit/" in html
    assert "confirmDeleteEvent" in html


def test_auth_status_pre_verification_with_session():
    """
    내부 시스템 /api/auth/status 엔드포인트가
    verify_admin_session 검증을 거쳐 관리자 상태를 올바르게 판별하는지 검증
    """
    from unittest.mock import AsyncMock

    # 1. 미인증 상태
    client.cookies.clear()
    res1 = client.get(f"{DEFAULT_PREFIX}/api/auth/status")
    assert res1.status_code == 200
    assert res1.json()["is_manager"] is False
    assert res1.json()["authenticated"] is False

    # 2. 관리자 세션이 확인된 경우 (verify_admin_session AsyncMock)
    with patch("app.routers.admin_router.verify_admin_session", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        client.cookies.set("auth_session", "valid_admin_token")
        res2 = client.get(f"{DEFAULT_PREFIX}/api/auth/status")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["is_manager"] is True
        assert data2["is_admin"] is True
        assert data2["authenticated"] is True

    # 3. 일반 사용자 세션인 경우
    with patch("app.routers.admin_router.verify_admin_session", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = False
        client.cookies.set("auth_session", "normal_user_token")
        res3 = client.get(f"{DEFAULT_PREFIX}/api/auth/status")
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["is_manager"] is False
        assert data3["authenticated"] is False

    client.cookies.clear()


def test_admin_redirect_loop_breaker():
    """
    미인증 상태에서 /votes/create 첫 접근 시 303 리다이렉트 발생(auth_attempted=1 파라미터 부착)
    및 Keycloak을 거쳐 auth_attempted=1을 단 채로 돌아왔을 때 무한 루프를 방지하고 403 Forbidden으로 안전하게 중단하는지 검증
    """
    import urllib.parse
    client.cookies.clear()
    # 1. 첫 접근: 303 리다이렉트 (auth_attempted=1 파라미터 포함)
    res1 = client.get(f"{DEFAULT_PREFIX}/create", follow_redirects=False)
    assert res1.status_code == 303
    loc = urllib.parse.unquote(res1.headers.get("location", ""))
    assert "auth_attempted=1" in loc

    # 2. Keycloak에서 세션 없이 돌아온 재접근: 무한 루프 방지 403 차단 (JSON API 클라이언트)
    res2 = client.get(f"{DEFAULT_PREFIX}/create?auth_attempted=1", follow_redirects=False)
    assert res2.status_code == 403
    assert "관리자(Manager) 권한이 확인되지 않았습니다" in res2.json()["detail"]

    # 3. 브라우저(Accept: text/html) 요청 시 500 없이 403.html 정상 렌더링 및 자가 치유 스크립트 검증
    res3 = client.get(
        f"{DEFAULT_PREFIX}/create?auth_attempted=1",
        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9"},
        follow_redirects=False
    )
    assert res3.status_code == 403
    assert "관리자만 접근이 가능한 이벤트입니다" in res3.text
    assert "verifyAndSyncRemoteSession" in res3.text


def test_sync_remote_session_and_admin_page_access():
    """
    웹 스크립트가 원격 Keycloak verify-session에서 획득한 관리자 정보를
    POST /votes/api/auth/sync-session으로 전달했을 때,
    로컬호스트 쿠키가 정상 발급되고 /votes/create에 403 에러 없이 200 OK로 진입 가능한지 E2E 검증
    """
    client.cookies.clear()

    # 1. 사용자가 원격에서 얻은 실제 응답 페이로드
    remote_payload = {
        "valid": True,
        "is_manager": True,
        "is_super": True,
        "role_flag": "2",
        "roles": ["user", "manager", "admin", "super", "super_admin"],
        "has_required_role": True,
        "user": {
            "id": "4a354343-1b24-4295-82a6-1c2b6e253005",
            "username": "01055787363",
            "name": "양인창",
            "email": "plus.holyseeds@gmail.com"
        }
    }

    # 2. sync-session 엔드포인트 호출
    sync_res = client.post(f"{DEFAULT_PREFIX}/api/auth/sync-session", json=remote_payload)
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["status"] == "ok"
    assert sync_data["synced"] is True
    assert sync_data["is_manager"] is True
    assert "token" in sync_data

    # 쿠키 발급 확인
    assert "local_manager_token" in sync_res.cookies or "auth_session" in sync_res.cookies

    # 3. 발급된 세션으로 /votes/create 접근 시 403 Forbidden 없이 200 OK 렌더링 확인
    create_page = client.get(f"{DEFAULT_PREFIX}/create")
    assert create_page.status_code == 200
    assert "새 이벤트 개설" in create_page.text

    # 4. /votes/api/auth/status에서도 즉시 인증된 관리자로 인식되는지 확인
    status_res = client.get(f"{DEFAULT_PREFIX}/api/auth/status")
    assert status_res.status_code == 200
    assert status_res.json()["is_manager"] is True
    assert status_res.json()["authenticated"] is True

    client.cookies.clear()


def test_client_script_verify_and_sync_elements_present():
    """
    base.html 내에 웹 스크립트 기반 원격 verify-session 호출 및
    로컬 백엔드 sync-session 연동 함수가 올바르게 탑재되어 있는지 검증
    """
    res = client.get(f"{DEFAULT_PREFIX}/")
    assert res.status_code == 200
    html = res.text

    assert "verifyAndSyncRemoteSession()" in html
    assert "/api/auth/sync-session" in html
    assert "credentials: 'include'" in html
    assert "handleManagerAction" in html



