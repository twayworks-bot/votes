import asyncio
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.item import EventItem
from app.models.event import Event
from app.core.security import hash_pin, verify_pin
from app.services.image_service import delete_stored_image, delete_stored_images
from app.services import vdstream_service, fotostream_service


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
    image_paths: Optional[List[str]] = None,
    video_id: Optional[str] = None,
    video_stream_url: Optional[str] = None,
    video_status: Optional[str] = "COMPLETED",
    video_duration: Optional[int] = None,
    video_source: Optional[str] = None
) -> EventItem:
    """새 하위 참여 항목 등록 (단일/다중 이미지 1~4장 또는 VDSTREAM/FOTOSTREAM 동영상 지원)"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")
    if not event.is_active:
        raise HTTPException(status_code=400, detail="종료된 이벤트에는 새 항목을 등록할 수 없습니다.")

    pin_clean = str(pin).strip()
    if len(pin_clean) < 4:
        raise HTTPException(status_code=400, detail="핀번호는 4자리 이상이어야 합니다.")

    resolved_paths: List[str] = []
    if image_paths:
        resolved_paths = [p for p in image_paths if p]
    elif image_path:
        resolved_paths = [image_path]

    if media_type == "video":
        if not video_id or not video_stream_url:
            raise HTTPException(status_code=400, detail="동영상 등록 시 video_id와 스트림 URL이 필요합니다.")
        effective_source = video_source or ("fotostream" if "/fotostream/" in video_stream_url else "vdstream")
    else:
        media_type = "image"
        effective_source = None
        if not resolved_paths:
            raise HTTPException(status_code=400, detail="이미지 파일 등록은 필수입니다.")

    primary_image = resolved_paths[0] if resolved_paths else (image_path or "")
    serialized_paths = json.dumps(resolved_paths, ensure_ascii=False) if resolved_paths else None

    item = EventItem(
        event_id=event_id,
        title=title.strip(),
        description=description.strip() if description else "",
        media_type=media_type,
        image_path=primary_image,
        image_paths=serialized_paths,
        video_id=video_id,
        video_stream_url=video_stream_url,
        video_status=video_status,
        video_duration=video_duration,
        video_source=effective_source,
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
    new_image_paths: Optional[List[str]] = None,
    new_video_id: Optional[str] = None,
    new_video_stream_url: Optional[str] = None,
    new_video_source: Optional[str] = None,
    new_video_duration: Optional[int] = None
) -> EventItem:
    """하위 항목 수정 (핀번호 인증 필수)"""
    item = get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    # 종료된 이벤트인 경우 수정 불가
    if not item.event or not item.event.is_active:
        raise HTTPException(status_code=400, detail="종료된 이벤트의 항목은 수정할 수 없습니다.")

    if not verify_item_pin(item, pin):
        raise HTTPException(status_code=403, detail="핀번호가 일치하지 않습니다. 올바른 핀번호를 입력해주세요.")

    if title is not None and title.strip():
        item.title = title.strip()
    if description is not None:
        item.description = description.strip()

    # 다중/단일 이미지 교체인 경우
    resolved_new_paths: List[str] = []
    if new_image_paths:
        resolved_new_paths = [p for p in new_image_paths if p]
    elif new_image_path:
        resolved_new_paths = [new_image_path]

    if resolved_new_paths:
        old_paths = [p for p in item.image_list if p not in resolved_new_paths]
        if old_paths:
            delete_stored_images(old_paths)
        item.image_path = resolved_new_paths[0]
        item.image_paths = json.dumps(resolved_new_paths, ensure_ascii=False)
        if not (new_video_id and new_video_stream_url):
            item.media_type = "image"
            item.video_id = None
            item.video_stream_url = None
            item.video_source = None

    # 비디오 교체인 경우 (VDSTREAM 또는 FOTOSTREAM)
    if new_video_id and new_video_stream_url:
        item.video_id = new_video_id
        item.video_stream_url = new_video_stream_url
        item.media_type = "video"
        item.video_source = new_video_source or (
            "fotostream" if "/fotostream/" in new_video_stream_url else "vdstream"
        )
        if new_video_duration is not None:
            item.video_duration = new_video_duration

    db.commit()
    db.refresh(item)
    return item


async def delete_item(db: Session, item_id: int, pin: str) -> bool:
    """하위 항목 삭제 (핀번호 인증 필수, 다중 이미지 파일 및 원격 VDSTREAM/FOTOSTREAM 비디오 정리)"""
    item = get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    # 종료된 이벤트인 경우 삭제 불가
    if not item.event or not item.event.is_active:
        raise HTTPException(status_code=400, detail="종료된 이벤트의 항목은 삭제할 수 없습니다.")

    if not verify_item_pin(item, pin):
        raise HTTPException(status_code=403, detail="핀번호가 일치하지 않습니다. 올바른 핀번호를 입력해주세요.")

    # 1. 로컬 이미지 파일 삭제 (다중 이미지 포함)
    paths = item.image_list
    if paths:
        delete_stored_images(paths)
    elif item.image_path:
        delete_stored_image(item.image_path)

    # 2. 원격 비디오 파일 삭제 (FOTOSTREAM 또는 VDSTREAM 분기)
    if item.media_type == "video" and item.video_id:
        try:
            if item.video_source == "fotostream" or (item.video_stream_url and "/fotostream/" in item.video_stream_url):
                await fotostream_service.delete_remote_video(item.video_id)
            else:
                await vdstream_service.delete_remote_video(item.video_id)
        except Exception:
            pass

    db.delete(item)
    db.commit()
    return True
