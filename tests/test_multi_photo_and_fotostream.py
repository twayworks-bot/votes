import io
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import (
    DEFAULT_PREFIX,
    AUTH_URL,
    AUTH_VERIFY_URL,
    VDSTREAM_URL,
    FOTOSTREAM_URL,
)
from app.core.templates import templates
from app.core.database import init_db, SessionLocal
from app.core.auth import create_local_manager_token
from app.services import event_service, fotostream_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def _make_dummy_png_bytes(width: int = 400, height: int = 300, color=(120, 180, 240)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_dotenv_variables_and_template_globals():
    """
    .env 환경변수 로드 및 변수 보간(${AUTH_URL}), Jinja2 전역 변수 바인딩 검증
    """
    assert DEFAULT_PREFIX == "/votes"
    assert AUTH_URL.startswith("http")
    assert "${AUTH_URL}" not in AUTH_VERIFY_URL
    assert AUTH_VERIFY_URL == f"{AUTH_URL}/api/verify-session"
    assert VDSTREAM_URL.startswith("http")
    assert FOTOSTREAM_URL.startswith("http")

    # 템플릿 전역 변수 동기화 확인
    g = templates.env.globals
    assert g["auth_url"] == AUTH_URL
    assert g["auth_verify_url"] == AUTH_VERIFY_URL
    assert g["vdstream_url"] == VDSTREAM_URL
    assert g["fotostream_url"] == FOTOSTREAM_URL


def test_multi_photo_2_to_4_upload_card_collage_and_detail_thumbnails():
    """
    다중 사진(2장, 3장, 4장) 업로드 시:
    - 4장까지 서버에 WebP 리사이즈 저장 및 image_list 반환
    - 카드 갤러리 프리뷰 영역에서 2/3/4장 분할 그리드 노출
    - 상세보기 모달에서 한 장씩 선택하여 전체보기를 지원하는 UI 요소 검증
    """
    db = SessionLocal()
    event = event_service.get_event_by_slug(db, "bazaarposter")
    event_id = event.id
    db.close()

    # 3장 다중 사진 업로드 테스트
    img1 = _make_dummy_png_bytes(600, 400, (255, 100, 100))
    img2 = _make_dummy_png_bytes(600, 400, (100, 255, 100))
    img3 = _make_dummy_png_bytes(600, 400, (100, 100, 255))

    files = [
        ("images", ("photo1.png", io.BytesIO(img1), "image/png")),
        ("images", ("photo2.png", io.BytesIO(img2), "image/png")),
        ("images", ("photo3.png", io.BytesIO(img3), "image/png")),
    ]
    data = {
        "event_id": str(event_id),
        "title": "다중 사진 3장 참가 작품",
        "description": "3장의 사진을 한 번에 프리뷰하고 상세보기에서 개별 선택합니다.",
        "pin": "1234",
        "media_type": "image",
    }

    res = client.post(f"{DEFAULT_PREFIX}/api/items", data=data, files=files)
    assert res.status_code == 200, res.text
    item_json = res.json()
    item_id = item_json["id"]

    assert item_json["media_type"] == "image"
    assert len(item_json["image_list"]) == 3
    assert item_json["image_path"] == item_json["image_list"][0]

    # 상세 조회 API 검증
    detail_res = client.get(f"{DEFAULT_PREFIX}/api/items/{item_id}")
    assert detail_res.status_code == 200
    detail_json = detail_res.json()
    assert len(detail_json["image_list"]) == 3

    # 이벤트 상세 페이지 HTML 내 3장 분할 그리드 프리뷰 및 상세 모달 썸네일 선택기 존재 검증
    page_res = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
    assert page_res.status_code == 200
    html = page_res.text
    assert "사진 3장" in html
    for img_rel in item_json["image_list"]:
        assert img_rel in html
    assert "modal-detail-thumbnails" in html
    assert "selectDetailPhoto" in html
    assert "stepDetailPhoto" in html

    # 4장 사진으로 수정(교체) 테스트
    files_4 = [
        ("images", ("p1.png", io.BytesIO(img1), "image/png")),
        ("images", ("p2.png", io.BytesIO(img2), "image/png")),
        ("images", ("p3.png", io.BytesIO(img3), "image/png")),
        ("images", ("p4.png", io.BytesIO(img1), "image/png")),
    ]
    upd_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/{item_id}/update",
        data={
            "pin": "1234",
            "title": "다중 사진 4장 수정 작품",
            "description": "4장으로 교체됨",
        },
        files=files_4,
    )
    assert upd_res.status_code == 200, upd_res.text
    upd_json = upd_res.json()
    assert len(upd_json["image_list"]) == 4

    page_res_4 = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
    assert "사진 4장" in page_res_4.text

    # 정리 (삭제)
    del_res = client.post(f"{DEFAULT_PREFIX}/api/items/{item_id}/delete", json={"pin": "1234"})
    assert del_res.status_code == 200


def test_event_disallow_multi_photo_blocks_multiple_uploads():
    """
    이벤트에 allow_multi_photo=False가 설정된 경우 2장 이상 사진 업로드 차단 검증
    """
    slug = f"single-only-{uuid.uuid4().hex[:6]}"
    token = create_local_manager_token({"username": "admin_tester"})
    client.cookies.set("local_manager_token", token)

    # allow_multi_photo 체크 없이(False) 이벤트 개설
    create_ev_res = client.post(
        f"{DEFAULT_PREFIX}/create",
        data={
            "slug": slug,
            "title": "단일 사진 전용 이벤트",
            "description": "다중 사진 비허용 테스트",
            "is_active": "true",
            "allow_comments": "true",
            # allow_multi_photo 생략 -> False
        },
        follow_redirects=False,
    )
    assert create_ev_res.status_code == 303

    db = SessionLocal()
    ev = event_service.get_event_by_slug(db, slug)
    assert ev is not None
    assert ev.allow_multi_photo is False
    ev_id = ev.id
    db.close()

    # 2장 업로드 시도 -> 400 에러 반환 확인
    img1 = _make_dummy_png_bytes(300, 300)
    img2 = _make_dummy_png_bytes(300, 300)
    res = client.post(
        f"{DEFAULT_PREFIX}/api/items",
        data={
            "event_id": str(ev_id),
            "title": "2장 시도",
            "description": "실패해야 함",
            "pin": "1234",
            "media_type": "image",
        },
        files=[
            ("images", ("a.png", io.BytesIO(img1), "image/png")),
            ("images", ("b.png", io.BytesIO(img2), "image/png")),
        ],
    )
    assert res.status_code == 400
    assert "다중 사진" in res.json()["detail"]

    # 테스트 이벤트 정리
    db = SessionLocal()
    event_service.delete_event(db, ev_id)
    db.close()
    client.cookies.clear()


def test_fotostream_5_plus_photos_conversion_and_item_lifecycle():
    """
    5장 이상 사진 업로드 시 FOTOSTREAM API를 통한 동영상 변환, HLS URL 해석,
    투표 항목 등록/조회/렌더링 및 삭제 시 원격 FOTOSTREAM 비디오 삭제 검증
    """
    db = SessionLocal()
    event = event_service.get_event_by_slug(db, "bazaarposter")
    event_id = event.id
    db.close()

    img_bytes = _make_dummy_png_bytes(500, 400, (80, 140, 220))

    # 1) 4장 이하로 fotostream/jobs 호출 시 400 반환 검증
    four_files = [
        ("images", (f"img_{i}.png", io.BytesIO(img_bytes), "image/png"))
        for i in range(4)
    ]
    bad_res = client.post(
        f"{DEFAULT_PREFIX}/api/items/fotostream/jobs",
        data={"title": "4장 테스트", "resolution": "1080p"},
        files=four_files,
    )
    assert bad_res.status_code == 400

    # 2) 5장 사진으로 fotostream/jobs 호출 (mocking create_slideshow_job)
    five_files = [
        ("images", (f"slide_{i}.png", io.BytesIO(img_bytes), "image/png"))
        for i in range(5)
    ]
    mock_job_resp = {
        "job_id": "job-uuid-5photos",
        "status": "QUEUED",
        "progress": 0,
        "video_id": None,
        "error_message": None,
    }
    with patch("app.services.fotostream_service.create_slideshow_job", new_callable=AsyncMock) as mock_create_job:
        mock_create_job.return_value = mock_job_resp
        job_res = client.post(
            f"{DEFAULT_PREFIX}/api/items/fotostream/jobs",
            data={"title": "5장 슬라이드쇼", "resolution": "1080p"},
            files=five_files,
        )
        assert job_res.status_code == 200, job_res.text
        job_json = job_res.json()
        assert job_json["status"] == "success"
        assert job_json["data"]["job_id"] == "job-uuid-5photos"
        assert job_json["preview_image_path"] is not None
        preview_image_path = job_json["preview_image_path"]
        mock_create_job.assert_called_once()

    # 3) 작업 상태 폴링 (GET /api/items/fotostream/jobs/{job_id})
    mock_status_resp = {
        "job_id": "job-uuid-5photos",
        "status": "COMPLETED",
        "progress": 100,
        "video_id": "fs-video-uuid-999",
        "error_message": None,
    }
    with patch("app.services.fotostream_service.get_job_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = mock_status_resp
        st_res = client.get(f"{DEFAULT_PREFIX}/api/items/fotostream/jobs/job-uuid-5photos")
        assert st_res.status_code == 200
        assert st_res.json()["data"]["status"] == "COMPLETED"
        assert st_res.json()["data"]["video_id"] == "fs-video-uuid-999"

    # 4) FOTOSTREAM 비디오 상세 조회 및 URL 해석 검증
    resolved_hls = fotostream_service._resolve_fotostream_media_url(
        "/fotostream/api/v1/videos/fs-video-uuid-999/hls/playlist.m3u8"
    )
    assert resolved_hls == f"{FOTOSTREAM_URL}/api/v1/videos/fs-video-uuid-999/hls/playlist.m3u8"

    mock_video_info = {
        "id": "fs-video-uuid-999",
        "title": "5장 슬라이드쇼",
        "duration": 15.0,
        "resolution": "1080p",
        "image_count": 5,
        "hls_url": "/fotostream/api/v1/videos/fs-video-uuid-999/hls/playlist.m3u8",
        "stream_url": "/fotostream/api/v1/videos/fs-video-uuid-999/stream",
        "thumbnail_url": "/fotostream/api/v1/videos/fs-video-uuid-999/thumbnail",
        "hls_absolute_url": resolved_hls,
        "stream_absolute_url": f"{FOTOSTREAM_URL}/api/v1/videos/fs-video-uuid-999/stream",
        "thumbnail_absolute_url": f"{FOTOSTREAM_URL}/api/v1/videos/fs-video-uuid-999/thumbnail",
    }
    with patch("app.services.fotostream_service.get_video_info", new_callable=AsyncMock) as mock_vinfo:
        mock_vinfo.return_value = mock_video_info
        v_res = client.get(f"{DEFAULT_PREFIX}/api/items/fotostream/videos/fs-video-uuid-999")
        assert v_res.status_code == 200
        v_data = v_res.json()["data"]
        assert v_data["hls_absolute_url"] == resolved_hls

    # 5) 변환된 FOTOSTREAM 동영상 스트림으로 투표 항목 생성
    create_item_res = client.post(
        f"{DEFAULT_PREFIX}/api/items",
        data={
            "event_id": str(event_id),
            "title": "5장 포토스트림 참가작",
            "description": "5장의 사진을 FOTOSTREAM으로 영상 변환한 항목입니다.",
            "pin": "5555",
            "media_type": "video",
            "video_id": "fs-video-uuid-999",
            "video_stream_url": resolved_hls,
            "video_duration": "15",
            "video_source": "fotostream",
            "preview_image_path": preview_image_path,
        },
    )
    assert create_item_res.status_code == 200, create_item_res.text
    created_item = create_item_res.json()
    fs_item_id = created_item["id"]
    assert created_item["media_type"] == "video"
    assert created_item["video_source"] == "fotostream"
    assert created_item["video_id"] == "fs-video-uuid-999"
    assert created_item["video_stream_url"] == resolved_hls
    assert created_item["image_path"] == preview_image_path

    # 6) 이벤트 상세 페이지에서 '포토스트림 영상' 배지 및 스트림 URL 노출 확인
    page_res = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
    assert page_res.status_code == 200
    assert "포토스트림 영상" in page_res.text
    assert resolved_hls in page_res.text

    # 7) 항목 삭제 시 fotostream_service.delete_remote_video가 호출되는지 검증
    with patch("app.services.fotostream_service.delete_remote_video", new_callable=AsyncMock) as mock_fs_del:
        mock_fs_del.return_value = True
        del_res = client.post(
            f"{DEFAULT_PREFIX}/api/items/{fs_item_id}/delete",
            json={"pin": "5555"},
        )
        assert del_res.status_code == 200
        mock_fs_del.assert_called_once_with("fs-video-uuid-999")


def test_fotostream_random_bgm_selection_in_job_creation():
    """
    FOTOSTREAM BGM 목록(GET /api/v1/bgm)에서 무작위로 하나를 선택하여
    영상 생성 요청(POST /api/v1/jobs) 시 bgm_id로 함께 전송하는지 검증
    """
    mock_bgm_tracks = [
        {"id": "bgm-uuid-001", "title": "Sunny Acoustic", "artist": "Pixabay", "mood": "Upbeat"},
        {"id": "bgm-uuid-002", "title": "Warm Memories", "artist": "Pixabay", "mood": "Cinematic"},
        {"id": "bgm-uuid-003", "title": "Joyful Moments", "artist": "Pixabay", "mood": "Happy"},
    ]

    # 1) BGM 목록 프록시 엔드포인트 검증
    with patch("app.services.fotostream_service.get_bgm_list", new_callable=AsyncMock) as mock_get_bgm:
        mock_get_bgm.return_value = mock_bgm_tracks
        bgm_res = client.get(f"{DEFAULT_PREFIX}/api/items/fotostream/bgm")
        assert bgm_res.status_code == 200
        bgm_json = bgm_res.json()
        assert bgm_json["status"] == "success"
        assert bgm_json["data"]["total"] == 3
        assert len(bgm_json["data"]["tracks"]) == 3

    # 2) create_slideshow_job 내부에서 get_bgm_list -> 무작위 BGM 선택 -> POST /api/v1/jobs 에 bgm_id 전달 검증
    captured_post_kwargs = {}

    class DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def json(self):
            return self._payload

    async def mock_httpx_get(self, url, *args, **kwargs):
        assert url == f"{FOTOSTREAM_URL}/api/v1/bgm"
        return DummyResponse(200, {"tracks": mock_bgm_tracks, "total": 3})

    async def mock_httpx_post(self, url, *args, **kwargs):
        assert url == f"{FOTOSTREAM_URL}/api/v1/jobs"
        captured_post_kwargs.update(kwargs)
        return DummyResponse(
            202,
            {
                "job_id": "job-with-random-bgm",
                "status": "QUEUED",
                "progress": 0,
            },
        )

    img_bytes = _make_dummy_png_bytes(400, 300, (120, 200, 150))
    five_files = [
        ("images", (f"bgm_slide_{i}.png", io.BytesIO(img_bytes), "image/png"))
        for i in range(5)
    ]

    with patch.object( fotostream_service.httpx.AsyncClient, "get", new=mock_httpx_get ), \
         patch.object( fotostream_service.httpx.AsyncClient, "post", new=mock_httpx_post ):
        job_res = client.post(
            f"{DEFAULT_PREFIX}/api/items/fotostream/jobs",
            data={"title": "BGM 합성 슬라이드쇼", "resolution": "1080p"},
            files=five_files,
        )
        assert job_res.status_code == 200, job_res.text
        res_json = job_res.json()
        data_obj = res_json["data"]

        # POST /api/v1/jobs 요청 시 data에 무작위 선택된 bgm_id가 포함되었는지 확인
        sent_form_data = captured_post_kwargs.get("data", {})
        assert "bgm_id" in sent_form_data
        assert sent_form_data["bgm_id"] in {"bgm-uuid-001", "bgm-uuid-002", "bgm-uuid-003"}

        # 응답에도 선택된 bgm_id 및 selected_bgm 메타데이터가 포함되었는지 확인
        assert data_obj["bgm_id"] == sent_form_data["bgm_id"]
        assert data_obj["selected_bgm"]["id"] == sent_form_data["bgm_id"]
        assert data_obj["selected_bgm"]["title"] in {"Sunny Acoustic", "Warm Memories", "Joyful Moments"}

