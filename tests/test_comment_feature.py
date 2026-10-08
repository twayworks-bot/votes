import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import DEFAULT_PREFIX
from app.core.database import SessionLocal, init_db
from app.models.event import Event
from app.models.item import EventItem, ItemComment
from app.services import event_service, item_service, comment_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_event_create_with_comment_option():
    """이벤트 생성 시 allow_comments 옵션 저장 및 검증"""
    db = SessionLocal()
    try:
        # 기존 테스트 이벤트가 남아있을 경우 정리
        for slug in ["test-comment-on", "test-comment-off"]:
            existing = event_service.get_event_by_slug(db, slug)
            if existing:
                db.delete(existing)
        db.commit()

        # 1. 댓글 허용 이벤트 생성
        ev_allowed = event_service.create_event(
            db=db,
            slug="test-comment-on",
            title="댓글 허용 이벤트",
            description="댓글이 허용되는 테스트 이벤트",
            allow_comments=True
        )
        assert ev_allowed.allow_comments is True

        # 2. 댓글 비활성화 이벤트 생성
        ev_disabled = event_service.create_event(
            db=db,
            slug="test-comment-off",
            title="댓글 차단 이벤트",
            description="댓글이 차단되는 테스트 이벤트",
            allow_comments=False
        )
        assert ev_disabled.allow_comments is False
    finally:
        db.close()


def test_comment_creation_and_validation():
    """댓글 작성 및 유효성 검사 (핀번호, 내용)"""
    db = SessionLocal()
    try:
        ev = event_service.get_event_by_slug(db, "test-comment-on")
        if not ev:
            ev = event_service.create_event(db=db, slug="test-comment-on", title="댓글 허용", allow_comments=True)
        
        # 테스트 항목 생성
        item = item_service.create_item(
            db=db,
            event_id=ev.id,
            title="댓글 테스트 항목",
            description="댓글 테스트 설명",
            pin="1234",
            media_type="image",
            image_path="test_item.jpg"
        )

        # 1. 정상 댓글 등록
        res = client.post(
            f"{DEFAULT_PREFIX}/api/items/{item.id}/comments",
            json={
                "author_name": "테스터",
                "content": "정말 훌륭한 작품입니다!",
                "pin": "5678"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["author_name"] == "테스터"
        assert data["content"] == "정말 훌륭한 작품입니다!"
        assert "pin_hash" not in data  # 응답에 핀 해시가 노출되지 않는지 확인
        comment_id = data["id"]

        # 2. 핀번호 4자리 미만 실패 검증
        res_short_pin = client.post(
            f"{DEFAULT_PREFIX}/api/items/{item.id}/comments",
            json={"author_name": "테스터", "content": "내용", "pin": "123"}
        )
        assert res_short_pin.status_code in (400, 422)

        # 3. 빈 내용 실패 검증
        res_empty = client.post(
            f"{DEFAULT_PREFIX}/api/items/{item.id}/comments",
            json={"author_name": "테스터", "content": "   ", "pin": "1234"}
        )
        assert res_empty.status_code == 400

        # 4. 댓글 목록 조회 검증
        list_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item.id}/comments")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["allow_comments"] is True
        assert list_data["total_count"] >= 1
        assert any(c["id"] == comment_id for c in list_data["comments"])

    finally:
        db.close()


def test_comment_forbidden_when_event_disallows():
    """이벤트 allow_comments=False인 경우 댓글 작성 차단 (403 Forbidden) 검증"""
    db = SessionLocal()
    try:
        ev = event_service.get_event_by_slug(db, "test-comment-off")
        if not ev:
            ev = event_service.create_event(db=db, slug="test-comment-off", title="댓글 차단", allow_comments=False)

        item = item_service.create_item(
            db=db,
            event_id=ev.id,
            title="차단 테스트 항목",
            description="차단 테스트 설명",
            pin="1234",
            media_type="image",
            image_path="test_block.jpg"
        )

        res = client.post(
            f"{DEFAULT_PREFIX}/api/items/{item.id}/comments",
            json={
                "author_name": "익명",
                "content": "댓글을 시도합니다.",
                "pin": "1234"
            }
        )
        assert res.status_code == 403
        assert "비활성화" in res.json()["detail"]

        # 조회 시 allow_comments=False 확인
        list_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item.id}/comments")
        assert list_res.status_code == 200
        assert list_res.json()["allow_comments"] is False

    finally:
        db.close()


def test_comment_deletion_with_pin():
    """댓글 핀번호 인증 삭제 검증 (수정 불가, 핀번호 일치 시 삭제만 가능)"""
    db = SessionLocal()
    try:
        ev = event_service.get_event_by_slug(db, "test-comment-on")
        item = item_service.create_item(
            db=db,
            event_id=ev.id,
            title="삭제 테스트 항목",
            description="삭제 테스트 설명",
            pin="1234",
            media_type="image",
            image_path="test_delete.jpg"
        )

        # 댓글 등록 (핀번호 9999)
        comment = comment_service.create_comment(
            db=db,
            item_id=item.id,
            content="삭제될 댓글입니다.",
            pin="9999",
            author_name="삭제대상"
        )
        comment_id = comment.id

        # 1. 틀린 핀번호 삭제 시도 -> 401 실패
        res_wrong = client.post(
            f"{DEFAULT_PREFIX}/api/items/comments/{comment_id}/delete",
            json={"pin": "0000"}
        )
        assert res_wrong.status_code == 401

        # 2. 올바른 핀번호 삭제 시도 -> 성공
        res_ok = client.post(
            f"{DEFAULT_PREFIX}/api/items/comments/{comment_id}/delete",
            json={"pin": "9999"}
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["success"] is True

        # 3. DB에서 실제로 삭제되었는지 확인
        deleted = db.query(ItemComment).filter(ItemComment.id == comment_id).first()
        assert deleted is None

    finally:
        db.close()


def test_ui_comments_elements_render():
    """이벤트 상세 페이지 HTML에서 댓글 버튼 및 모달 렌더링 확인"""
    # 1. 댓글 허용 이벤트
    res = client.get(f"{DEFAULT_PREFIX}/test-comment-on")
    assert res.status_code == 200
    html = res.text
    assert "simple-comment-modal" in html
    assert "comment-delete-modal" in html
    assert "detail-comment-form" in html
    assert "openSimpleCommentModal" in html
    assert "loadItemComments" in html

    # 2. 댓글 비활성화 이벤트
    res_off = client.get(f"{DEFAULT_PREFIX}/test-comment-off")
    assert res_off.status_code == 200
    html_off = res_off.text
    assert "이 이벤트는 댓글 작성이 비활성화되어 있습니다" in html_off
