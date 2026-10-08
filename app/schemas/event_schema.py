from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class EventBase(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64, description="URL Subpath용 고유 식별자")
    title: str = Field(..., min_length=1, max_length=200, description="이벤트 제목")
    description: Optional[str] = Field(None, description="이벤트 상세 안내 설명")
    is_active: bool = Field(True, description="이벤트 활성화 여부")
    allow_comments: bool = Field(True, description="댓글 달기 활성화 여부")


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    allow_comments: Optional[bool] = None


class EventResponse(EventBase):
    id: int
    cover_image: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    total_items: int = 0
    total_votes: int = 0

    model_config = ConfigDict(from_attributes=True)
