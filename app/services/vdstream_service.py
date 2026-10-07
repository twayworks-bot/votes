import logging
from typing import Optional, Dict, Any
import httpx
from fastapi import UploadFile, HTTPException

from app.core.config import VDSTREAM_BASE_URL, VDSTREAM_PIN

logger = logging.getLogger(__name__)


def _get_headers() -> Dict[str, str]:
    headers = {}
    if VDSTREAM_PIN:
        headers["X-App-Pin"] = VDSTREAM_PIN
    return headers


async def upload_video_file(file: UploadFile, title: Optional[str] = None) -> Dict[str, Any]:
    """
    VDSTREAM API로 비디오 파일을 업로드하고 작업 큐 등록 응답(202 Accepted)을 수신합니다.
    """
    url = f"{VDSTREAM_BASE_URL}/api/v1/videos/upload"
    headers = _get_headers()

    filename = file.filename or "uploaded_video.mp4"
    content_type = file.content_type or "video/mp4"

    file_bytes = await file.read()
    await file.seek(0)

    files = {
        "file": (filename, file_bytes, content_type)
    }
    data = {}
    if title:
        data["title"] = title

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, files=files, data=data)
            if response.status_code not in (200, 201, 202):
                logger.error(f"VDSTREAM Upload Error: {response.status_code} {response.text}")
                detail = "비디오 업로드에 실패했습니다."
                try:
                    err_json = response.json()
                    detail = err_json.get("detail") or err_json.get("message") or detail
                except Exception:
                    pass
                raise HTTPException(status_code=response.status_code, detail=detail)

            res_json = response.json()
            return res_json.get("data", res_json)
        except httpx.RequestError as exc:
            logger.error(f"VDSTREAM Connection Error during upload: {exc}")
            raise HTTPException(status_code=502, detail=f"스트리밍 서버와 통신할 수 없습니다: {exc}")


async def get_video_status(video_id: str) -> Dict[str, Any]:
    """
    비디오의 트랜스코딩 진행 상태를 조회합니다. (QUEUED, PROCESSING, COMPLETED, FAILED)
    """
    url = f"{VDSTREAM_BASE_URL}/api/v1/videos/{video_id}/status"
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.error(f"VDSTREAM Status Error: {response.status_code} {response.text}")
                raise HTTPException(status_code=response.status_code, detail="비디오 상태 조회 실패")

            res_json = response.json()
            return res_json.get("data", res_json)
        except httpx.RequestError as exc:
            logger.error(f"VDSTREAM Connection Error during status check: {exc}")
            raise HTTPException(status_code=502, detail="스트리밍 서버 연결 오류")


async def get_stream_info(video_id: str) -> Dict[str, Any]:
    """
    트랜스코딩 완료된 비디오의 스트리밍 URL 및 시청 세션을 발급받습니다.
    """
    url = f"{VDSTREAM_BASE_URL}/api/v1/videos/{video_id}/stream"
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.error(f"VDSTREAM Stream Info Error: {response.status_code} {response.text}")
                detail = "스트리밍 정보 조회 실패"
                try:
                    err_json = response.json()
                    detail = err_json.get("detail") or err_json.get("message") or detail
                except Exception:
                    pass
                raise HTTPException(status_code=response.status_code, detail=detail)

            res_json = response.json()
            return res_json.get("data", res_json)
        except httpx.RequestError as exc:
            logger.error(f"VDSTREAM Connection Error during stream info: {exc}")
            raise HTTPException(status_code=502, detail="스트리밍 서버 연결 오류")


async def send_heartbeat(session_id: str) -> Dict[str, Any]:
    """
    활성 스트리밍 세션의 수명을 연장하기 위해 15초 주기로 하트비트를 전송합니다.
    """
    url = f"{VDSTREAM_BASE_URL}/api/v1/streams/{session_id}/heartbeat"
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, headers=headers)
            if response.status_code != 200:
                logger.warning(f"VDSTREAM Heartbeat Error: {response.status_code}")
                return {"success": False, "status": response.status_code}
            return response.json()
        except Exception as exc:
            logger.warning(f"VDSTREAM Heartbeat request failed: {exc}")
            return {"success": False, "error": str(exc)}


async def release_session(session_id: str) -> Dict[str, Any]:
    """
    시청 종료 시 스트리밍 슬롯(최대 5개)을 즉시 반환합니다.
    """
    url = f"{VDSTREAM_BASE_URL}/api/v1/streams/{session_id}/release"
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, headers=headers)
            if response.status_code != 200:
                logger.warning(f"VDSTREAM Release Error: {response.status_code}")
                return {"success": False, "status": response.status_code}
            return response.json()
        except Exception as exc:
            logger.warning(f"VDSTREAM Release request failed: {exc}")
            return {"success": False, "error": str(exc)}


async def delete_remote_video(video_id: str) -> bool:
    """
    VDSTREAM에서 해당 비디오 및 관련 HLS/MP4 파일들을 영구 삭제합니다.
    """
    if not video_id:
        return False
    url = f"{VDSTREAM_BASE_URL}/api/v1/videos/{video_id}"
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.delete(url, headers=headers)
            return response.status_code in (200, 204)
        except Exception as exc:
            logger.error(f"VDSTREAM Delete Error for {video_id}: {exc}")
            return False
