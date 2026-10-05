from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.core.config import DEFAULT_PREFIX, AUTH_URL
from app.core.database import get_db
from app.core.templates import templates
from app.core.auth import (
    verify_auth_session,
    build_login_url,
    build_logout_url
)
from app.services import event_service, item_service

router = APIRouter()


@router.get("/{eventName}", response_class=HTMLResponse)
def view_event_page(
    eventName: str,
    request: Request,
    sort: str = Query("newest", pattern="^(newest|popular)$"),
    db: Session = Depends(get_db)
):
    """
    이벤트 전용 랜딩 및 참여 갤러리 페이지 (Subpath 라우팅: /votes/{eventName})
    인증 세션을 확인하여 상단 네비게이션에 올바른 로그인/로그아웃 URL 및 권한 상태를 전달합니다.
    """
    auth_info = verify_auth_session(request)
    current_url = str(request.url)
    user = auth_info.get("user")
    is_manager = auth_info.get("is_manager", False)
    login_url = build_login_url(current_url, require_role="manager")
    logout_url = build_logout_url(current_url)

    event = event_service.get_event_by_slug(db, eventName)
    if not event:
        return templates.TemplateResponse(
            request=request,
            name="event/404.html",
            context={
                "default_prefix": DEFAULT_PREFIX,
                "auth": auth_info,
                "user": user,
                "is_manager": is_manager,
                "auth_url": AUTH_URL,
                "login_url": login_url,
                "logout_url": logout_url,
            },
            status_code=404
        )

    items = item_service.get_items_by_event(db, event.id, sort=sort)
    total_votes = sum(item.vote_count for item in items)

    return templates.TemplateResponse(
        request=request,
        name="event/detail.html",
        context={
            "event": event,
            "items": items,
            "total_votes": total_votes,
            "sort": sort,
            "default_prefix": DEFAULT_PREFIX,
            "auth": auth_info,
            "user": user,
            "is_manager": is_manager,
            "auth_url": AUTH_URL,
            "login_url": login_url,
            "logout_url": logout_url,
        }
    )
