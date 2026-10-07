import asyncio
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.item import EventItem
from app.core.security import hash_pin, verify_pin
from app.services.image_service import delete_stored_image
from app.services import vdstream_service


def get_items_by_event(db: Session, event_id: int, sort: str = "newest") -> List[EventItem]:
    """이벤트에 속한 하위 항목 목록 조회 (최신순 또는 인기투표순)"""
    query = db.query(EventItem).filter(EventItem.event_id == event_id)
    if sort == "popular":
        # 인기순 (투표수 내림차순, 동일 시 최신순)
        return query.order_by(EventItem.vote_count.desc(), EventItem.id.desc()).all()
    # 기본: 최신 등록순
    return query.order_by(EventItem.id.desc()).all()


def get_item_by_id(db: Session, item_id: int) -> Optional[EventItem]:
    """ID로 항목 조회"""
    return db.query(EventItem).filter(EventItem.id == item_id).first()


def create_item(
    db: Session,
    event_id: int,
    title: str,
    description: Optional[str],
    pin: str,
    media_type: str = "image",
    image_path: Optional[str] = None,
    video_id: Optional[str] = None,
    video_stream_url: Optional[str] = None,
    video_status: Optional[str] = "COMPLETED",
    video_duration: Optional[int] = None
) -> EventItem:
    """새 하위 참여 항목 등록 (이미지 또는 동영상 지원)"""
    pin_clean = str(pin).strip()
    if len(pin_clean) < 4:
        raise HTTPException(status_code=400, detail="핀번호는 4자리 이상이어야 합니다.")

    if media_type == "video":
        if not video_id or not video_stream_url:
            raise HTTPException(status_code=400, detail="동영상 등록 시 video_id와 스트림 URL이 필요합니다.")
    else:
        media_type = "image"
        if not image_path:
            raise HTTPException(status_code=400, detail="이미지 파일 등록은 필수입니다.")

    item = EventItem(
        event_id=event_id,
        title=title.strip(),
        description=description.strip() if description else "",
        media_type=media_type,
        image_path=image_path or "",
        video_id=video_id,
        video_stream_url=video_stream_url,
        video_status=video_status,
        video_duration=video_duration,
        pin_hash=hash_pin(pin_clean),
        vote_count=0
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def verify_item_pin(item: EventItem, pin: str) -> bool:
    """핀번호 검증 헬퍼"""
    return verify_pin(pin, item.pin_hash)


def update_item(
    db: Session,
    item_id: int,
    pin: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    new_image_path: Optional[str] = None,
    new_video_id: Optional[str] = None,
    new_video_stream_url: Optional[str] = None
) -> EventItem:
    """하위 항목 수정 (핀번호 인증 필수)"""
    item = get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    if not verify_item_pin(item, pin):
        raise HTTPException(status_code=403, detail="핀번호가 일치하지 않습니다. 올바른 핀번호를 입력해주세요.")

    if title is not None and title.strip():
        item.title = title.strip()
    if description is not None:
        item.description = description.strip()

    # 이미지 교체인 경우
    if new_image_path is not None:
        if item.image_path and item.image_path != new_image_path:
            delete_stored_image(item.image_path)
        item.image_path = new_image_path
        item.media_type = "image"

    # 비디오 교체인 경우
    if new_video_id and new_video_stream_url:
        item.video_id = new_video_id
        item.video_stream_url = new_video_stream_url
        item.media_type = "video"

    db.commit()
    db.refresh(item)
    return item


async def delete_item(db: Session, item_id: int, pin: str) -> bool:
    """하위 항목 삭제 (핀번호 인증 필수, 이미지 파일 및 원격 VDSTREAM 비디오 정리)"""
    item = get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    if not verify_item_pin(item, pin):
        raise HTTPException(status_code=403, detail="핀번호가 일치하지 않습니다. 올바른 핀번호를 입력해주세요.")

    # 1. 로컬 이미지 파일 삭제
    if item.image_path:
        delete_stored_image(item.image_path)

    # 2. VDSTREAM 원격 비디오 파일 삭제
    if item.media_type == "video" and item.video_id:
        try:
            await vdstream_service.delete_remote_video(item.video_id)
        except Exception:
            pass

    db.delete(item)
    db.commit()
    return True
