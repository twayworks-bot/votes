from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class CommentCreate(BaseModel):
    author_name: Optional[str] = Field("익명", max_length=50, description="작성자 닉네임")
    content: str = Field(..., min_length=1, max_length=1000, description="댓글 내용")
    pin: str = Field(..., min_length=4, max_length=32, description="삭제용 핀번호 (4자리 이상)")


class CommentDelete(BaseModel):
    pin: str = Field(..., min_length=1, max_length=32, description="삭제 인증용 핀번호")


class CommentResponse(BaseModel):
    id: int
    item_id: int
    author_name: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    allow_comments: bool
    comments: List[CommentResponse]
    total_count: int
