from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.item import EventItem, ItemComment
from app.core.security import hash_pin, verify_pin


def get_comments_by_item(db: Session, item_id: int) -> List[ItemComment]:
    """해당 참여 항목의 댓글 목록 조회 (최신 등록순)"""
    return db.query(ItemComment).filter(ItemComment.item_id == item_id).order_by(ItemComment.id.desc()).all()


def get_comment_by_id(db: Session, comment_id: int) -> Optional[ItemComment]:
    """ID로 댓글 단건 조회"""
    return db.query(ItemComment).filter(ItemComment.id == comment_id).first()


def create_comment(
    db: Session,
    item_id: int,
    content: str,
    pin: str,
    author_name: Optional[str] = "익명"
) -> ItemComment:
    """새 댓글 등록 (이벤트의 allow_comments 검증 및 핀번호 암호화)"""
    item = db.query(EventItem).filter(EventItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="참여 항목을 찾을 수 없습니다.")

    # 상위 이벤트 댓글 허용 옵션 검증
    if not item.event or not item.event.allow_comments:
        raise HTTPException(
            status_code=403,
            detail="이 이벤트는 댓글 작성이 비활성화되어 있습니다."
        )

    clean_content = content.strip() if content else ""
    if not clean_content:
        raise HTTPException(status_code=400, detail="댓글 내용을 입력해주세요.")

    clean_pin = pin.strip() if pin else ""
    if len(clean_pin) < 4:
        raise HTTPException(status_code=400, detail="삭제용 핀번호는 4자리 이상이어야 합니다.")

    clean_author = (author_name.strip() if author_name and author_name.strip() else "익명")[:50]

    comment = ItemComment(
        item_id=item_id,
        author_name=clean_author,
        content=clean_content,
        pin_hash=hash_pin(clean_pin)
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment_id: int, pin: str) -> int:
    """핀번호 인증 후 댓글 삭제 (수정은 불가, 핀번호 일치 시 삭제만 가능)"""
    comment = get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="삭제할 댓글을 찾을 수 없습니다.")

    clean_pin = pin.strip() if pin else ""
    if not clean_pin or not verify_pin(clean_pin, comment.pin_hash):
        raise HTTPException(status_code=401, detail="핀번호가 일치하지 않습니다.")

    item_id = comment.item_id
    db.delete(comment)
    db.commit()

    # 삭제 후 잔여 댓글 수 반환
    remaining_count = db.query(ItemComment).filter(ItemComment.item_id == item_id).count()
    return remaining_count
