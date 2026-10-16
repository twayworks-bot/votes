import json
from datetime import datetime, timezone
from typing import List
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class EventItem(Base):
    __tablename__ = "event_items"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # 미디어 타입 구분 ('image' | 'video')
    media_type = Column(String(20), default="image", nullable=False)
    image_path = Column(String(255), nullable=True, default="")
    # 다중 사진 등록 시(2~4장) 전체 이미지 상대 경로 JSON 배열 문자열
    image_paths = Column(Text, nullable=True)

    # 비디오 관련 필드 (media_type == 'video'인 경우: 'vdstream' 또는 'fotostream')
    video_id = Column(String(64), nullable=True, index=True)
    video_stream_url = Column(String(500), nullable=True)
    video_status = Column(String(30), default="COMPLETED", nullable=True)
    video_duration = Column(Integer, nullable=True)
    video_source = Column(String(30), nullable=True, default="vdstream")

    pin_hash = Column(String(128), nullable=False)
    vote_count = Column(Integer, default=0, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # N:1 관계 (상위 이벤트)
    event = relationship("Event", back_populates="items")
    # 1:N 관계 (투표 로그)
    votes = relationship("VoteLog", back_populates="item", cascade="all, delete-orphan")
    # 1:N 관계 (댓글 목록: 최신 등록순)
    comments = relationship("ItemComment", back_populates="item", cascade="all, delete-orphan", order_by="desc(ItemComment.id)")

    @property
    def image_list(self) -> List[str]:
        """등록된 이미지 경로 리스트를 반환합니다 (다중 사진 2~4장 또는 단일 사진)."""
        if self.image_paths:
            try:
                parsed = json.loads(self.image_paths)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return [str(p) for p in parsed if p]
            except Exception:
                pass
        if self.image_path:
            return [self.image_path]
        return []

    @property
    def comment_count(self) -> int:
        return len(self.comments) if self.comments else 0


class VoteLog(Base):
    __tablename__ = "vote_logs"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("event_items.id", ondelete="CASCADE"), nullable=False, index=True)
    voter_id = Column(String(64), nullable=False, index=True)  # 브라우저 세션 ID 또는 클라이언트 IP 식별자
    created_at = Column(DateTime, default=utc_now)

    item = relationship("EventItem", back_populates="votes")


class ItemComment(Base):
    __tablename__ = "item_comments"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("event_items.id", ondelete="CASCADE"), nullable=False, index=True)
    author_name = Column(String(50), nullable=False, default="익명")
    content = Column(Text, nullable=False)
    pin_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    item = relationship("EventItem", back_populates="comments")
