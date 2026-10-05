from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    cover_image = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # 1:N 관계 (하위 참여 항목들)
    items = relationship("EventItem", back_populates="event", cascade="all, delete-orphan", order_by="desc(EventItem.id)")

    @property
    def total_votes(self) -> int:
        return sum(item.vote_count for item in self.items)

    @property
    def total_items(self) -> int:
        return len(self.items)
