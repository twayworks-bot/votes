import io
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import DEFAULT_PREFIX
from app.core.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_video_proxy_upload():
    """비디오 프록시 업로드 엔드포인트 검증 (mocking vdstream_service)"""
    mock_upload_res = {
        "video_id": "vid_20261007_test123",
        "filename": "sample_intro.mp4",
        "status": "QUEUED",
        "queue_position": 1
    }

    with patch("app.services.vdstream_service.upload_video_file", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = mock_upload_res

        dummy_video = io.BytesIO(b"fake-mp4-data-stream-bytes")
        files = {"file": ("sample_intro.mp4", dummy_video, "video/mp4")}
        data = {"title": "샘플 영상 제목"}

        response = client.post(f"{DEFAULT_PREFIX}/api/items/video/upload", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        assert res_json["data"]["video_id"] == "vid_20261007_test123"
        mock_upload.assert_called_once()


def test_video_proxy_status():
    """비디오 프록시 상태 조회 엔드포인트 검증"""
    mock_status_res = {
        "video_id": "vid_20261007_test123",
        "status": "PROCESSING",
        "progress_percent": 65.5,
        "is_ready": False
    }

    with patch("app.services.vdstream_service.get_video_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = mock_status_res

        response = client.get(f"{DEFAULT_PREFIX}/api/items/video/vid_20261007_test123/status")
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        assert res_json["data"]["status"] == "PROCESSING"
        assert res_json["data"]["progress_percent"] == 65.5


def test_video_proxy_stream_info():
    """비디오 스트리밍 정보 및 세션 조회 검증"""
    mock_stream_res = {
        "video_id": "vid_20261007_test123",
        "session_id": "sess_abc_123",
        "streaming_urls": {
            "hls_absolute_url": "https://holyseeds.thewayworks.net/vdstream/api/v1/streams/vid_20261007_test123/master.m3u8?session_id=sess_abc_123",
            "mp4_range_url": "https://holyseeds.thewayworks.net/vdstream/api/v1/streams/vid_20261007_test123/mp4?session_id=sess_abc_123"
        }
    }

    with patch("app.services.vdstream_service.get_stream_info", new_callable=AsyncMock) as mock_stream:
        mock_stream.return_value = mock_stream_res

        response = client.get(f"{DEFAULT_PREFIX}/api/items/video/vid_20261007_test123/stream")
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        assert "master.m3u8" in res_json["data"]["streaming_urls"]["hls_absolute_url"]


def test_create_and_view_video_item_lifecycle():
    """
    동영상 참여 항목 생성, 카드 프리뷰 렌더링, 상세 조회, 삭제 전체 라이프사이클 E2E 검증
    """
    # 1. 동영상 참여 항목 생성 (bazaarposter 이벤트 대상)
    from app.core.database import SessionLocal
    from app.services import event_service
    db = SessionLocal()
    event = event_service.get_event_by_slug(db, "bazaarposter")
    event_id = event.id
    db.close()

    video_stream_url = "https://holyseeds.thewayworks.net/vdstream/api/v1/streams/vid_test_lifecycle/master.m3u8"
    create_data = {
        "event_id": event_id,
        "title": "청소년 찬양 동영상 참가작",
        "description": "청소년부에서 제작한 고화질 찬양 영상입니다.",
        "pin": "9876",
        "media_type": "video",
        "video_id": "vid_test_lifecycle",
        "video_stream_url": video_stream_url,
        "video_duration": 180
    }

    create_res = client.post(f"{DEFAULT_PREFIX}/api/items", data=create_data)
    assert create_res.status_code == 200, create_res.text
    item_json = create_res.json()
    item_id = item_json["id"]
    assert item_json["media_type"] == "video"
    assert item_json["video_id"] == "vid_test_lifecycle"
    assert item_json["video_stream_url"] == video_stream_url

    # 2. 항목 단건 조회 (GET /api/items/{id})
    detail_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item_id}")
    assert detail_res.status_code == 200
    detail_json = detail_res.json()
    assert detail_json["title"] == "청소년 찬양 동영상 참가작"
    assert detail_json["media_type"] == "video"

    # 3. 이벤트 랜딩 페이지 렌더링 확인 (동영상 카드 프리뷰 및 뱃지 확인)
    page_res = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
    assert page_res.status_code == 200
    page_html = page_res.text
    assert "청소년 찬양 동영상 참가작" in page_html
    assert f"card-video-{item_id}" in page_html
    assert "동영상" in page_html
    assert video_stream_url in page_html

    # 4. 항목 삭제 (DELETE with PIN)
    with patch("app.services.vdstream_service.delete_remote_video", new_callable=AsyncMock) as mock_del:
        mock_del.return_value = True

        # 잘못된 핀번호 시도
        bad_del_res = client.post(
            f"{DEFAULT_PREFIX}/api/items/{item_id}/delete",
            json={"pin": "0000"}
        )
        assert bad_del_res.status_code == 403

        # 올바른 핀번호로 삭제
        del_res = client.post(
            f"{DEFAULT_PREFIX}/api/items/{item_id}/delete",
            json={"pin": "9876"}
        )
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True
        mock_del.assert_called_once_with("vid_test_lifecycle")

    # 5. 삭제 확인 (404)
    check_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item_id}")
    assert check_res.status_code == 404
