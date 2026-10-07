from datetime import datetime, timezone
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

    # 비디오 관련 필드 (media_type == 'video'인 경우)
    video_id = Column(String(64), nullable=True, index=True)
    video_stream_url = Column(String(500), nullable=True)
    video_status = Column(String(30), default="COMPLETED", nullable=True)
    video_duration = Column(Integer, nullable=True)

    pin_hash = Column(String(128), nullable=False)
    vote_count = Column(Integer, default=0, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # N:1 관계 (상위 이벤트)
    event = relationship("Event", back_populates="items")
    # 1:N 관계 (투표 로그)
    votes = relationship("VoteLog", back_populates="item", cascade="all, delete-orphan")


class VoteLog(Base):
    __tablename__ = "vote_logs"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("event_items.id", ondelete="CASCADE"), nullable=False, index=True)
    voter_id = Column(String(64), nullable=False, index=True)  # 브라우저 세션 ID 또는 클라이언트 IP 식별자
    created_at = Column(DateTime, default=utc_now)

    item = relationship("EventItem", back_populates="votes")
