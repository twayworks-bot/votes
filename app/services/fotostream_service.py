import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import httpx
from fastapi import UploadFile, HTTPException

from app.core.config import FOTOSTREAM_URL

logger = logging.getLogger(__name__)


def _resolve_fotostream_media_url(path_or_url: Optional[str]) -> str:
    """
    FOTOSTREAM API가 반환하는 상대 경로(예: /fotostream/api/v1/videos/{id}/hls/playlist.m3u8)를
    FOTOSTREAM_URL 기준의 완전한 절대 URL로 변환합니다.
    """
    if not path_or_url:
        return ""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url

    parsed = urlparse(FOTOSTREAM_URL)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    base_prefix = parsed.path.rstrip("/")  # 예: '/fotostream'

    clean_path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
    if base_prefix and clean_path.startswith(base_prefix + "/"):
        return f"{origin}{clean_path}"
    return f"{FOTOSTREAM_URL}{clean_path}"


async def create_slideshow_job(
    files: List[UploadFile],
    title: Optional[str] = None,
    resolution: str = "1080p",
    bgm_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    다중 사진(5장 ~ 49장)을 FOTOSTREAM API(POST /api/v1/jobs)로 업로드하여
    비동기 동영상 합성 작업을 큐에 등록하고 job_id를 반환합니다.
    """
    if not files or len(files) < 1:
        raise HTTPException(status_code=400, detail="변환할 이미지 파일이 제공되지 않았습니다.")
    if len(files) > 49:
        raise HTTPException(status_code=400, detail="FOTOSTREAM 영상 변환은 최대 49장까지 지원합니다.")

    url = f"{FOTOSTREAM_URL}/api/v1/jobs"
    multipart_files = []

    for idx, f in enumerate(files):
        filename = f.filename or f"photo_{idx + 1}.jpg"
        content_type = f.content_type or "image/jpeg"
        await f.seek(0)
        file_bytes = await f.read()
        await f.seek(0)
        if not file_bytes:
            continue
        multipart_files.append(("images", (filename, file_bytes, content_type)))

    if not multipart_files:
        raise HTTPException(status_code=400, detail="유효한 이미지 파일이 없습니다.")

    data = {
        "title": title or "VoteEvent Slideshow",
        "resolution": resolution or "1080p",
    }
    if bgm_id:
        data["bgm_id"] = bgm_id

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(url, files=multipart_files, data=data)
            if response.status_code not in (200, 201, 202):
                logger.error(f"FOTOSTREAM Job Create Error: {response.status_code} {response.text}")
                detail = "FOTOSTREAM 동영상 변환 작업 등록에 실패했습니다."
                try:
                    err_json = response.json()
                    detail = err_json.get("detail") or err_json.get("message") or detail
                except Exception:
                    pass
                raise HTTPException(status_code=response.status_code, detail=detail)

            res_json = response.json()
            return res_json.get("data", res_json)
        except httpx.RequestError as exc:
            logger.error(f"FOTOSTREAM Connection Error during job creation: {exc}")
            raise HTTPException(status_code=502, detail=f"FOTOSTREAM 서버와 통신할 수 없습니다: {exc}")


async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    FOTOSTREAM 작업의 진행 상태(QUEUED, PROCESSING, COMPLETED, FAILED) 및 진행률(0~100%)을 조회합니다.
    """
    url = f"{FOTOSTREAM_URL}/api/v1/jobs/{job_id}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url)
            if response.status_code != 200:
                logger.error(f"FOTOSTREAM Job Status Error: {response.status_code} {response.text}")
                raise HTTPException(status_code=response.status_code, detail="FOTOSTREAM 작업 상태 조회 실패")

            res_json = response.json()
            return res_json.get("data", res_json)
        except httpx.RequestError as exc:
            logger.error(f"FOTOSTREAM Connection Error during job status check: {exc}")
            raise HTTPException(status_code=502, detail="FOTOSTREAM 서버 연결 오류")


async def get_video_info(video_id: str) -> Dict[str, Any]:
    """
    합성이 완료된 FOTOSTREAM 비디오의 상세 메타데이터 및 HLS/MP4 스트리밍 URL을 조회합니다.
    """
    url = f"{FOTOSTREAM_URL}/api/v1/videos/{video_id}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url)
            if response.status_code != 200:
                logger.error(f"FOTOSTREAM Video Info Error: {response.status_code} {response.text}")
                raise HTTPException(status_code=response.status_code, detail="FOTOSTREAM 비디오 정보 조회 실패")

            res_json = response.json()
            video_data = res_json.get("data", res_json)

            raw_hls = video_data.get("hls_url") or f"/api/v1/videos/{video_id}/hls/playlist.m3u8"
            raw_stream = video_data.get("stream_url") or f"/api/v1/videos/{video_id}/stream"
            raw_thumb = video_data.get("thumbnail_url") or f"/api/v1/videos/{video_id}/thumbnail"

            video_data["hls_absolute_url"] = _resolve_fotostream_media_url(raw_hls)
            video_data["stream_absolute_url"] = _resolve_fotostream_media_url(raw_stream)
            video_data["thumbnail_absolute_url"] = _resolve_fotostream_media_url(raw_thumb)
            return video_data
        except httpx.RequestError as exc:
            logger.error(f"FOTOSTREAM Connection Error during video info: {exc}")
            raise HTTPException(status_code=502, detail="FOTOSTREAM 서버 연결 오류")


async def delete_remote_video(video_id: str) -> bool:
    """
    FOTOSTREAM 서버에서 비디오 DB 레코드 및 물리 파일(MP4, HLS 세그먼트, 썸네일)을 영구 삭제합니다.
    """
    if not video_id:
        return False
    url = f"{FOTOSTREAM_URL}/api/v1/videos/{video_id}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.delete(url)
            return response.status_code in (200, 204)
        except Exception as exc:
            logger.error(f"FOTOSTREAM Delete Error for {video_id}: {exc}")
            return False
