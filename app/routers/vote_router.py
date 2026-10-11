import uuid
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import verify_auth_session
from app.services import vote_service, item_service

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
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

    auth_info = verify_auth_session(request)
    is_manager = auth_info.get("is_manager", False)

    if item.event and item.event.manager_only and not is_manager:
        return {
            "success": False,
            "already_voted": False,
            "message": "관리자 전용 이벤트입니다. 일반 사용자나 익명사용자는 접근이 허용되지 않습니다.",
            "item_id": item.id,
            "vote_count": 0
        }

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

    if item.event and item.event.hide_vote_counts and not is_manager:
        result["vote_count"] = 0

    return result
