from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.item_schema import ItemResponse, ItemVerifyPin
from app.schemas.comment_schema import CommentCreate, CommentResponse, CommentDelete, CommentListResponse
from app.services import item_service, image_service, vdstream_service, comment_service

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
# 2. 참여 항목 CRUD 엔드포인트 (이미지 및 동영상 지원)
# =====================================================================

@router.post("", response_model=ItemResponse)
async def create_item_endpoint(
    event_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    pin: str = Form(...),
    media_type: str = Form("image"),
    image: Optional[UploadFile] = File(None),
    video_id: Optional[str] = Form(None),
    video_stream_url: Optional[str] = Form(None),
    video_duration: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """참여 항목 등록 (이미지 1920px 리사이즈 또는 VDSTREAM 비디오 지원)"""
    image_path = None

    if media_type == "video":
        if not video_id or not video_stream_url:
            raise HTTPException(status_code=400, detail="동영상 등록을 위해 video_id와 스트림 URL이 필요합니다.")
    else:
        media_type = "image"
        if not image or not image.filename:
            raise HTTPException(status_code=400, detail="작품 이미지 파일은 필수입니다.")
        image_path = await image_service.save_upload_image(image, folder_type="items")

    item = item_service.create_item(
        db=db,
        event_id=event_id,
        title=title,
        description=description,
        pin=pin,
        media_type=media_type,
        image_path=image_path,
        video_id=video_id,
        video_stream_url=video_stream_url,
        video_status="COMPLETED" if media_type == "video" else None,
        video_duration=video_duration
    )
    return item


@router.get("/{item_id}", response_model=ItemResponse)
def get_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    """항목 상세 정보 조회 (모달용)"""
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    return item


@router.post("/{item_id}/update", response_model=ItemResponse)
async def update_item_endpoint(
    item_id: int,
    pin: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    video_id: Optional[str] = Form(None),
    video_stream_url: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """항목 수정 (핀번호 인증 필수)"""
    new_image_path = None
    if image and image.filename:
        new_image_path = await image_service.save_upload_image(image, folder_type="items")

    updated_item = item_service.update_item(
        db=db,
        item_id=item_id,
        pin=pin,
        title=title,
        description=description,
        new_image_path=new_image_path,
        new_video_id=video_id,
        new_video_stream_url=video_stream_url
    )
    return updated_item


@router.post("/{item_id}/delete")
async def delete_item_endpoint(
    item_id: int,
    body: ItemVerifyPin,
    db: Session = Depends(get_db)
):
    """항목 삭제 (핀번호 인증 필수 및 원격 비디오/로컬 이미지 정리)"""
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
