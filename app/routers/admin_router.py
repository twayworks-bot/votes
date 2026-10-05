from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.core.config import DEFAULT_PREFIX, BASE_DIR, AUTH_URL
from app.core.database import get_db
from app.core.auth import (
    verify_auth_session,
    require_manager_web,
    build_login_url,
    build_logout_url
)
from app.services import event_service, image_service

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
def list_events_page(request: Request, db: Session = Depends(get_db)):
    """관리자 이벤트 목록 페이지 (로그인 여부 및 매니저 권한 전달)"""
    events = event_service.get_all_events(db)
    auth_info = verify_auth_session(request)
    current_url = str(request.url)

    return templates.TemplateResponse(
        request=request,
        name="admin/event_list.html",
        context={
            "events": events,
            "default_prefix": DEFAULT_PREFIX,
            "auth": auth_info,
            "user": auth_info.get("user"),
            "is_manager": auth_info.get("is_manager", False),
            "auth_url": AUTH_URL,
            "login_url": build_login_url(current_url, require_role="manager"),
            "logout_url": build_logout_url(current_url),
        }
    )


@router.get("/create", response_class=HTMLResponse)
def create_event_page(
    request: Request,
    auth_info: dict = Depends(require_manager_web)
):
    """새 이벤트 개설 폼 페이지 (manager flag=1 이상 필수)"""
    current_url = str(request.url)
    return templates.TemplateResponse(
        request=request,
        name="admin/event_form.html",
        context={
            "is_edit": False,
            "event": None,
            "default_prefix": DEFAULT_PREFIX,
            "error": None,
            "auth": auth_info,
            "user": auth_info.get("user"),
            "is_manager": True,
            "auth_url": AUTH_URL,
            "logout_url": build_logout_url(f"{DEFAULT_PREFIX}/"),
        }
    )


@router.post("/create")
async def create_event_action(
    request: Request,
    slug: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    auth_info: dict = Depends(require_manager_web)
):
    """새 이벤트 생성 처리 (manager 권한 필요)"""
    try:
        cover_path = None
        if cover_image and cover_image.filename:
            cover_path = await image_service.save_upload_image(cover_image, folder_type="covers")

        event_service.create_event(
            db=db,
            slug=slug,
            title=title,
            description=description,
            cover_image=cover_path
        )
        return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=303)
    except Exception as e:
        detail_msg = getattr(e, "detail", str(e))
        return templates.TemplateResponse(
            request=request,
            name="admin/event_form.html",
            context={
                "is_edit": False,
                "event": {"slug": slug, "title": title, "description": description},
                "default_prefix": DEFAULT_PREFIX,
                "error": detail_msg,
                "auth": auth_info,
                "user": auth_info.get("user"),
                "is_manager": True,
                "auth_url": AUTH_URL,
                "logout_url": build_logout_url(f"{DEFAULT_PREFIX}/"),
            },
            status_code=400
        )


@router.get("/edit/{event_id}", response_class=HTMLResponse)
def edit_event_page(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    auth_info: dict = Depends(require_manager_web)
):
    """이벤트 수정 폼 페이지 (manager 권한 필요)"""
    event = event_service.get_event_by_id(db, event_id)
    if not event:
        return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/event_form.html",
        context={
            "is_edit": True,
            "event": event,
            "default_prefix": DEFAULT_PREFIX,
            "error": None,
            "auth": auth_info,
            "user": auth_info.get("user"),
            "is_manager": True,
            "auth_url": AUTH_URL,
            "logout_url": build_logout_url(f"{DEFAULT_PREFIX}/"),
        }
    )


@router.post("/edit/{event_id}")
async def edit_event_action(
    event_id: int,
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(False),
    cover_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    auth_info: dict = Depends(require_manager_web)
):
    """이벤트 정보 수정 처리 (manager 권한 필요)"""
    try:
        cover_path = None
        if cover_image and cover_image.filename:
            cover_path = await image_service.save_upload_image(cover_image, folder_type="covers")

        event_service.update_event(
            db=db,
            event_id=event_id,
            title=title,
            description=description,
            cover_image=cover_path,
            is_active=bool(is_active)
        )
        return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=303)
    except Exception as e:
        detail_msg = getattr(e, "detail", str(e))
        event = event_service.get_event_by_id(db, event_id)
        return templates.TemplateResponse(
            request=request,
            name="admin/event_form.html",
            context={
                "is_edit": True,
                "event": event,
                "default_prefix": DEFAULT_PREFIX,
                "error": detail_msg,
                "auth": auth_info,
                "user": auth_info.get("user"),
                "is_manager": True,
                "auth_url": AUTH_URL,
                "logout_url": build_logout_url(f"{DEFAULT_PREFIX}/"),
            },
            status_code=400
        )


@router.post("/delete/{event_id}")
def delete_event_action(
    event_id: int,
    db: Session = Depends(get_db),
    auth_info: dict = Depends(require_manager_web)
):
    """이벤트 삭제 처리 (manager 권한 필요)"""
    event_service.delete_event(db, event_id)
    return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=303)
