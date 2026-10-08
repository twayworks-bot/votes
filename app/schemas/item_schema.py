from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="항목 제목")
    description: Optional[str] = Field(None, description="항목 상세 설명")


class ItemCreate(ItemBase):
    pin: str = Field(..., min_length=4, max_length=32, description="수정/삭제용 핀번호 (4자리 이상)")


class ItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    pin: str = Field(..., description="작성 시 설정한 핀번호")


class ItemVerifyPin(BaseModel):
    pin: str = Field(..., description="작성 시 설정한 핀번호")


class ItemResponse(ItemBase):
    id: int
    event_id: int
    media_type: str = "image"
    image_path: Optional[str] = None
    video_id: Optional[str] = None
    video_stream_url: Optional[str] = None
    video_status: Optional[str] = None
    video_duration: Optional[int] = None
    vote_count: int
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
