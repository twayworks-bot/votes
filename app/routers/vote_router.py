import uuid
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import vote_service

router = APIRouter(prefix="/api/items", tags=["vote"])


@router.post("/{item_id}/vote")
def vote_item_endpoint(
    item_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    좋아요(투표) 비동기 API 엔드포인트
    브라우저 쿠키 또는 IP 기반 식별자를 통해 1차 중복 방지를 지원합니다.
    """
    voter_id = request.cookies.get("voteevent_voter_id")
    if not voter_id:
        # 클라이언트 식별 쿠키 발급 (1년 유지)
        client_ip = request.client.host if request.client else "unknown"
        voter_id = f"{uuid.uuid4().hex[:16]}_{hash(client_ip) % 10000}"
        response.set_cookie(
            key="voteevent_voter_id",
            value=voter_id,
            max_age=365 * 24 * 3600,
            httponly=True,
            samesite="lax"
        )

    result = vote_service.register_vote(db=db, item_id=item_id, voter_id=voter_id)
    return result
