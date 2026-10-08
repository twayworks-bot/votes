import re
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.event import Event
from app.services.image_service import delete_stored_image


def validate_slug(slug: str) -> str:
    """이벤트 식별자(Slug) 유효성 검사 (영문자, 숫자, 하이픈, 언더스코어만 허용)"""
    slug_clean = slug.strip()
    if not re.match(r"^[a-zA-Z0-9_\-]+$", slug_clean):
        raise HTTPException(
            status_code=400,
            detail="이벤트 식별자(이름)는 영문자, 숫자, 하이픈(-), 언더스코어(_)만 사용 가능합니다."
        )
    # 시스템 예약어 방어
    reserved = {"admin", "api", "static", "uploads", "favicon.ico"}
    if slug_clean.lower() in reserved:
        raise HTTPException(status_code=400, detail=f"'{slug_clean}'은(는) 시스템 예약어로 사용할 수 없습니다.")
    return slug_clean


def get_all_events(db: Session) -> List[Event]:
    """모든 이벤트 목록 조회 (최신 등록순)"""
    return db.query(Event).order_by(Event.id.desc()).all()


def get_event_by_id(db: Session, event_id: int) -> Optional[Event]:
    """ID로 이벤트 조회"""
    return db.query(Event).filter(Event.id == event_id).first()


def get_event_by_slug(db: Session, slug: str) -> Optional[Event]:
    """식별자(Slug/Name)로 이벤트 조회 (대소문자 무시 검색 지원)"""
    return db.query(Event).filter(Event.slug.ilike(slug)).first()


def create_event(
    db: Session,
    slug: str,
    title: str,
    description: Optional[str] = None,
    cover_image: Optional[str] = None,
    allow_comments: bool = True
) -> Event:
    """새 이벤트 생성"""
    clean_slug = validate_slug(slug)
    existing = get_event_by_slug(db, clean_slug)
    if existing:
        raise HTTPException(status_code=400, detail=f"이미 존재하는 이벤트 이름(식별자)입니다: {clean_slug}")

    event = Event(
        slug=clean_slug,
        title=title.strip(),
        description=description.strip() if description else "",
        cover_image=cover_image,
        is_active=True,
        allow_comments=allow_comments
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(
    db: Session,
    event_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    cover_image: Optional[str] = None,
    is_active: Optional[bool] = None,
    allow_comments: Optional[bool] = None
) -> Event:
    """이벤트 메타데이터 수정"""
    event = get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")

    if title is not None:
        event.title = title.strip()
    if description is not None:
        event.description = description.strip()
    if cover_image is not None:
        if event.cover_image and event.cover_image != cover_image:
            delete_stored_image(event.cover_image)
        event.cover_image = cover_image
    if is_active is not None:
        event.is_active = is_active
    if allow_comments is not None:
        event.allow_comments = allow_comments

    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event_id: int) -> bool:
    """이벤트 및 연관된 하위 항목, 업로드 이미지 파일 일괄 삭제"""
    event = get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")

    # 1. 이벤트 대표 커버 이미지 삭제
    if event.cover_image:
        delete_stored_image(event.cover_image)

    # 2. 하위 항목들에 포함된 모든 이미지 파일 삭제
    for item in event.items:
        if item.image_path:
            delete_stored_image(item.image_path)

    # 3. DB 연쇄 삭제 (Cascade)
    db.delete(event)
    db.commit()
    return True
