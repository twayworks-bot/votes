from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.item import EventItem, VoteLog


def register_vote(db: Session, item_id: int, voter_id: str) -> dict:
    """
    특정 참여 항목에 좋아요(투표)를 행사합니다.
    동일 클라이언트(voter_id)에 대한 중복 투표 방지 및 집계 처리를 수행합니다.
    """
    item = db.query(EventItem).filter(EventItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    # 동일 브라우저/식별자의 중복 투표 여부 확인
    existing_vote = db.query(VoteLog).filter(
        VoteLog.item_id == item_id,
        VoteLog.voter_id == voter_id
    ).first()

    if existing_vote:
        # 이미 투표한 경우 안내와 함께 현재 투표수 반환
        return {
            "success": False,
            "already_voted": True,
            "message": "이미 이 항목에 투표하셨습니다.",
            "item_id": item.id,
            "vote_count": item.vote_count
        }

    # 신규 투표 로그 기록 및 카운트 증가
    vote_log = VoteLog(item_id=item.id, voter_id=voter_id)
    db.add(vote_log)
    item.vote_count = (item.vote_count or 0) + 1

    db.commit()
    db.refresh(item)

    return {
        "success": True,
        "already_voted": False,
        "message": "투표가 성공적으로 반영되었습니다!",
        "item_id": item.id,
        "vote_count": item.vote_count
    }
