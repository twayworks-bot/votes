from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import verify_auth_session
from app.models.event import Event
from app.schemas.item_schema import ItemResponse, ItemVerifyPin
from app.schemas.comment_schema import CommentCreate, CommentResponse, CommentDelete, CommentListResponse
from app.services import item_service, image_service, vdstream_service, fotostream_service, comment_service

router = APIRouter(prefix="/api/items", tags=["items"])


# =====================================================================
# 1. VDSTREAM 비디오 프록시 엔드포인트
# =====================================================================

@router.post("/video/upload")
async def upload_video_proxy(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None)
):
    """
    VDSTREAM으로 동영상 파일을 중계 업로드하고 작업 ID를 발급받습니다.
    (최대 100MB, 10분 이내 권장)
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="동영상 파일이 선택되지 않았습니다.")
    
    result = await vdstream_service.upload_video_file(file, title)
    return {"status": "success", "data": result}


@router.get("/video/{video_id}/status")
async def get_video_status_proxy(video_id: str):
    """
    비디오의 트랜스코딩 진행 상태를 중계 조회합니다. (QUEUED, PROCESSING, COMPLETED, FAILED)
    """
    status_data = await vdstream_service.get_video_status(video_id)
    return {"status": "success", "data": status_data}


@router.get("/video/{video_id}/stream")
async def get_stream_info_proxy(video_id: str):
    """
    트랜스코딩 완료된 비디오의 스트리밍 URL 및 시청 세션을 발급받습니다.
    """
    stream_data = await vdstream_service.get_stream_info(video_id)
    return {"status": "success", "data": stream_data}


@router.post("/video/heartbeat/{session_id}")
async def heartbeat_proxy(session_id: str):
    """
    재생 중 세션 슬롯 유지를 위한 15초 주기 하트비트 중계
    """
    result = await vdstream_service.send_heartbeat(session_id)
    return result


@router.post("/video/release/{session_id}")
async def release_proxy(session_id: str):
    """
    재생 종료 시 스트리밍 슬롯을 즉시 반환합니다.
    """
    result = await vdstream_service.release_session(session_id)
    return result


# =====================================================================
# 1-2. FOTOSTREAM 다중 사진(5장 이상) -> 동영상 스트림 변환 프록시 엔드포인트
# =====================================================================

@router.post("/fotostream/jobs")
async def create_fotostream_job_proxy(
    images: List[UploadFile] = File(...),
    title: Optional[str] = Form(None),
    resolution: str = Form("1080p")
):
    """
    다중 사진(5장 ~ 49장)을 FOTOSTREAM 엔진으로 전송하여 슬라이드쇼/매트릭스 영상 합성 작업을 등록합니다.
    첫 번째 사진은 대표 썸네일 이미지로도 로컬 저장하여 함께 반환합니다.
    """
    valid_files = [f for f in (images or []) if f and f.filename]
    if len(valid_files) < 5:
        raise HTTPException(
            status_code=400,
            detail="FOTOSTREAM 영상 변환은 5장 이상의 사진 등록 시에만 지원됩니다. (1~4장은 사진 프리뷰로 등록)"
        )
    if len(valid_files) > 49:
        raise HTTPException(status_code=400, detail="사진은 최대 49장까지 업로드할 수 있습니다.")

    # 첫 번째 이미지를 대표 썸네일/폴백용으로 저장
    preview_image_path = await image_service.save_upload_image(valid_files[0], folder_type="items")

    try:
        job_result = await fotostream_service.create_slideshow_job(
            files=valid_files,
            title=title or "VoteEvent Photo Stream",
            resolution=resolution
        )
        job_result["preview_image_path"] = preview_image_path
        return {"status": "success", "preview_image_path": preview_image_path, "data": job_result}
    except Exception:
        image_service.delete_stored_image(preview_image_path)
        raise


@router.get("/fotostream/jobs/{job_id}")
async def get_fotostream_job_status_proxy(job_id: str):
    """
    FOTOSTREAM 합성 작업의 진행 상태(QUEUED, PROCESSING, COMPLETED, FAILED) 및 진행률(0~100)을 조회합니다.
    """
    status_data = await fotostream_service.get_job_status(job_id)
    return {"status": "success", "data": status_data}


@router.get("/fotostream/videos/{video_id}")
async def get_fotostream_video_info_proxy(video_id: str):
    """
    합성 완료된 FOTOSTREAM 비디오의 HLS(.m3u8) 및 MP4 스트리밍 URL 정보를 조회합니다.
    """
    video_data = await fotostream_service.get_video_info(video_id)
    return {"status": "success", "data": video_data}


# =====================================================================
# 2. 참여 항목 CRUD 엔드포인트 (단일/다중 이미지 1~4장 및 5장+ FOTOSTREAM / VDSTREAM 동영상 지원)
# =====================================================================

def _collect_valid_upload_files(
    single_image: Optional[UploadFile],
    multi_images: Optional[List[UploadFile]]
) -> List[UploadFile]:
    """단일 image 필드와 다중 images 필드에서 유효한 UploadFile 목록을 순서대로 추출합니다."""
    collected: List[UploadFile] = []
    if multi_images:
        for f in multi_images:
            if f and f.filename:
                collected.append(f)
    if single_image and single_image.filename:
        # 이미 동일한 객체가 들어있지 않은 경우에만 추가
        if single_image not in collected:
            collected.append(single_image)
    return collected


@router.post("", response_model=ItemResponse)
async def create_item_endpoint(
    request: Request,
    event_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    pin: str = Form(...),
    media_type: str = Form("image"),
    image: Optional[UploadFile] = File(None),
    images: Optional[List[UploadFile]] = File(None),
    preview_image_path: Optional[str] = Form(None),
    video_id: Optional[str] = Form(None),
    video_stream_url: Optional[str] = Form(None),
    video_duration: Optional[int] = Form(None),
    video_source: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    참여 항목 등록:
    - 사진 1장: 단일 사진 저장
    - 사진 2~4장: 다중 사진 저장 (카드 프리뷰에서 한번에 보기, 상세보기에서 한장씩 선택 전체보기)
    - 사진 5장 이상: FOTOSTREAM을 통해 변환된 동영상 스트림 등록
    - 동영상 파일: VDSTREAM을 통해 트랜스코딩된 동영상 스트림 등록
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")
    if event.manager_only:
        auth_info = verify_auth_session(request)
        if not auth_info.get("is_manager"):
            raise HTTPException(status_code=403, detail="관리자 전용 이벤트입니다. 일반 사용자나 익명사용자는 접근이 허용되지 않습니다.")

    saved_paths: List[str] = []
    effective_media_type = media_type
    effective_video_source = video_source

    if media_type == "video":
        if not video_id or not video_stream_url:
            raise HTTPException(status_code=400, detail="동영상 등록을 위해 video_id와 스트림 URL이 필요합니다.")
        if preview_image_path:
            saved_paths = [preview_image_path]
        if not effective_video_source:
            effective_video_source = "fotostream" if "/fotostream/" in video_stream_url else "vdstream"
    else:
        upload_list = _collect_valid_upload_files(image, images)
        if not upload_list:
            raise HTTPException(status_code=400, detail="작품 이미지 파일은 최소 1장 이상 필수입니다.")

        if len(upload_list) > 1 and not getattr(event, "allow_multi_photo", True):
            raise HTTPException(status_code=400, detail="이 이벤트는 다중 사진 등록이 비활성화되어 있어 1장의 사진만 등록할 수 있습니다.")

        if len(upload_list) >= 5:
            raise HTTPException(
                status_code=400,
                detail="5장 이상의 사진은 FOTOSTREAM 동영상 변환 완료 후 등록할 수 있습니다."
            )

        effective_media_type = "image"
        saved_paths = await image_service.save_multiple_upload_images(upload_list, folder_type="items")

    item = item_service.create_item(
        db=db,
        event_id=event_id,
        title=title,
        description=description,
        pin=pin,
        media_type=effective_media_type,
        image_path=saved_paths[0] if saved_paths else None,
        image_paths=saved_paths if saved_paths else None,
        video_id=video_id,
        video_stream_url=video_stream_url,
        video_status="COMPLETED" if effective_media_type == "video" else None,
        video_duration=video_duration,
        video_source=effective_video_source
    )
    return item


@router.get("/{item_id}", response_model=ItemResponse)
def get_item_endpoint(item_id: int, request: Request, db: Session = Depends(get_db)):
    """항목 상세 정보 조회 (모달용)"""
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    auth_info = verify_auth_session(request)
    is_manager = auth_info.get("is_manager", False)
    if item.event and item.event.manager_only and not is_manager:
        raise HTTPException(status_code=403, detail="관리자 전용 이벤트입니다. 일반 사용자나 익명사용자는 접근이 허용되지 않습니다.")

    resp = ItemResponse.model_validate(item)
    if item.event and item.event.hide_vote_counts and not is_manager:
        resp.vote_count = 0
    return resp


@router.post("/{item_id}/update", response_model=ItemResponse)
async def update_item_endpoint(
    item_id: int,
    request: Request,
    pin: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    images: Optional[List[UploadFile]] = File(None),
    preview_image_path: Optional[str] = Form(None),
    video_id: Optional[str] = Form(None),
    video_stream_url: Optional[str] = Form(None),
    video_source: Optional[str] = Form(None),
    video_duration: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """항목 수정 (핀번호 인증 필수, 단일/다중 사진 및 동영상 교체 지원)"""
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    if item.event and item.event.manager_only:
        auth_info = verify_auth_session(request)
        if not auth_info.get("is_manager"):
            raise HTTPException(status_code=403, detail="관리자 전용 이벤트입니다. 일반 사용자나 익명사용자는 접근이 허용되지 않습니다.")

    upload_list = _collect_valid_upload_files(image, images)
    new_image_paths: Optional[List[str]] = None

    if upload_list:
        if len(upload_list) > 1 and item.event and not getattr(item.event, "allow_multi_photo", True):
            raise HTTPException(status_code=400, detail="이 이벤트는 다중 사진 등록이 비활성화되어 있어 1장의 사진만 등록할 수 있습니다.")
        if len(upload_list) >= 5:
            raise HTTPException(status_code=400, detail="5장 이상의 사진은 FOTOSTREAM 동영상 변환 완료 후 등록해주세요.")
        new_image_paths = await image_service.save_multiple_upload_images(upload_list, folder_type="items")
    elif preview_image_path:
        new_image_paths = [preview_image_path]

    updated_item = item_service.update_item(
        db=db,
        item_id=item_id,
        pin=pin,
        title=title,
        description=description,
        new_image_path=new_image_paths[0] if new_image_paths else None,
        new_image_paths=new_image_paths,
        new_video_id=video_id,
        new_video_stream_url=video_stream_url,
        new_video_source=video_source,
        new_video_duration=video_duration
    )
    return updated_item


@router.post("/{item_id}/delete")
async def delete_item_endpoint(
    item_id: int,
    body: ItemVerifyPin,
    request: Request,
    db: Session = Depends(get_db)
):
    """항목 삭제 (핀번호 인증 필수 및 원격 비디오/로컬 이미지 정리)"""
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    if item.event and item.event.manager_only:
        auth_info = verify_auth_session(request)
        if not auth_info.get("is_manager"):
            raise HTTPException(status_code=403, detail="관리자 전용 이벤트입니다. 일반 사용자나 익명사용자는 접근이 허용되지 않습니다.")

    success = await item_service.delete_item(db=db, item_id=item_id, pin=body.pin)
    return {"success": success, "message": "성공적으로 삭제되었습니다."}


# =====================================================================
# 3. 항목 댓글 (Comment) 엔드포인트 (핀번호 삭제 및 이벤트 옵션 제어)
# =====================================================================

@router.get("/{item_id}/comments", response_model=CommentListResponse)
def get_comments_endpoint(
    item_id: int,
    db: Session = Depends(get_db)
):
    """항목의 댓글 목록 조회 (이벤트의 allow_comments 활성화 여부 포함)"""
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    allow_comments = bool(item.event and item.event.allow_comments)
    comments = comment_service.get_comments_by_item(db, item_id)
    return {
        "allow_comments": allow_comments,
        "comments": comments,
        "total_count": len(comments)
    }


@router.post("/{item_id}/comments", response_model=CommentResponse)
def create_comment_endpoint(
    item_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db)
):
    """항목에 새 댓글 작성 (핀번호 필수 등록, 수정은 불가하며 삭제만 가능)"""
    new_comment = comment_service.create_comment(
        db=db,
        item_id=item_id,
        content=body.content,
        pin=body.pin,
        author_name=body.author_name
    )
    return new_comment


@router.post("/comments/{comment_id}/delete")
@router.post("/{item_id}/comments/{comment_id}/delete")
def delete_comment_endpoint(
    comment_id: int,
    body: CommentDelete,
    db: Session = Depends(get_db)
):
    """핀번호 인증을 통한 댓글 삭제"""
    remaining_count = comment_service.delete_comment(
        db=db,
        comment_id=comment_id,
        pin=body.pin
    )
    return {
        "success": True,
        "message": "댓글이 삭제되었습니다.",
        "comment_count": remaining_count
    }
