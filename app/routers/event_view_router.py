from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.core.config import DEFAULT_PREFIX, BASE_DIR
from app.core.database import get_db
from app.services import event_service, item_service

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/{eventName}", response_class=HTMLResponse)
def view_event_page(
    eventName: str,
    request: Request,
    sort: str = Query("newest", pattern="^(newest|popular)$"),
    db: Session = Depends(get_db)
):
    """
    이벤트 전용 랜딩 및 참여 갤러리 페이지 (Subpath 라우팅: /votes/{eventName})
    """
    event = event_service.get_event_by_slug(db, eventName)
    if not event:
        return templates.TemplateResponse(
            request=request,
            name="event/404.html",
            context={
                "default_prefix": DEFAULT_PREFIX,
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
        }
    )
