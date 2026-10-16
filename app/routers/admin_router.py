from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.core.config import DEFAULT_PREFIX, AUTH_URL
from app.core.database import get_db
from app.core.templates import templates
from app.core.auth import (
    verify_auth_session,
    require_manager_web,
    build_login_url,
    build_logout_url,
    verify_admin_session,
    extract_auth_session,
    create_local_manager_token,
    verify_local_manager_token
)
from app.services import event_service, image_service
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/api/auth/sync-session")
async def sync_remote_session(request: Request):
    """
    웹 스크립트(Client JS)가 원격 Keycloak(AUTH_VERIFY_URL)에서 직접 검증받은 결과를 전달받아
    로컬호스트(localhost) 도메인에 관리자 세션 쿠키를 동기화/발급합니다.
    이를 통해 도메인 간 브라우저 쿠키 격리 문제를 완벽히 해결합니다.
    """
    try:
        data = await request.json()
    except Exception:
        data = dict(request.query_params)

    is_valid = bool(data.get("valid") is True or str(data.get("valid")).lower() == "true")
    roles = data.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    role_flag = str(data.get("role_flag", "")).strip()

    is_manager = bool(
        data.get("is_manager") is True
        or data.get("is_super") is True
        or data.get("has_required_role") is True
        or role_flag in ("1", "2")
        or ("manager" in roles)
        or ("super" in roles)
        or ("admin" in roles)
    )

    if not (is_valid and is_manager):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "유효한 관리자 세션 정보가 아닙니다.", "synced": False}
        )

    user_info = data.get("user") or {}
    token = create_local_manager_token(user_data=user_info)

    response = JSONResponse(
        content={
            "status": "ok",
            "synced": True,
            "is_manager": True,
            "user": user_info,
            "token": token
        }
    )
    # localhost 도메인 쿠키 발급
    response.set_cookie(
        key="local_manager_token",
        value=token,
        path="/",
        samesite="lax",
        max_age=86400
    )
    response.set_cookie(
        key="auth_session",
        value=token,
        path="/",
        samesite="lax",
        max_age=86400
    )
    return response


@router.get("/api/auth/status")
async def get_auth_status(request: Request):
    """
    클라이언트의 세션을 확인하고 매니저(관리자) 로그인 여부를 반환합니다.
    (다른 서비스 규격과 일치하는 매니저 상태 검증 엔드포인트)
    """
    auth_session = extract_auth_session(request)
    is_admin = await verify_admin_session(auth_session)
    user_info = None
    if is_admin or auth_session:
        auth_data = verify_auth_session(request)
        if auth_data.get("is_manager"):
            is_admin = True
        user_info = auth_data.get("user")

    return {
        "is_admin": is_admin,
        "is_manager": is_admin,
        "authenticated": bool(auth_session and is_admin),
        "user": user_info
    }


@router.get("/", response_class=HTMLResponse)
async def list_events_page(request: Request, db: Session = Depends(get_db)):
    """관리자 이벤트 목록 페이지 (사전 세션 검증 및 매니저 권한 전달)"""
    events = event_service.get_all_events(db)
    auth_session = extract_auth_session(request)
    is_admin = await verify_admin_session(auth_session)

    auth_info = verify_auth_session(request)
    if is_admin:
        auth_info["is_manager"] = True
    is_manager = bool(auth_info.get("is_manager") or is_admin)
    current_url = str(request.url)

    return templates.TemplateResponse(
        request=request,
        name="admin/event_list.html",
        context={
            "events": events,
            "default_prefix": DEFAULT_PREFIX,
            "auth": auth_info,
            "user": auth_info.get("user"),
            "is_manager": is_manager,
            "auth_url": AUTH_URL,
            "login_url": build_login_url(current_url, require_role="manager"),
            "logout_url": build_logout_url(current_url),
        }
    )


@router.get("/create", response_class=HTMLResponse)
async def create_event_page(
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
    allow_comments: Optional[str] = Form(None),
    manager_only: Optional[str] = Form(None),
    hide_vote_counts: Optional[str] = Form(None),
    allow_multi_photo: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    auth_info: dict = Depends(require_manager_web)
):
    """새 이벤트 생성 처리 (manager 권한 필요)"""
    try:
        cover_path = None
        if cover_image and cover_image.filename:
            cover_path = await image_service.save_upload_image(cover_image, folder_type="covers")

        is_comments_allowed = bool(allow_comments)
        is_manager_only = bool(manager_only)
        is_hide_vote_counts = bool(hide_vote_counts)
        is_allow_multi_photo = bool(allow_multi_photo)

        event_service.create_event(
            db=db,
            slug=slug,
            title=title,
            description=description,
            cover_image=cover_path,
            allow_comments=is_comments_allowed,
            manager_only=is_manager_only,
            hide_vote_counts=is_hide_vote_counts,
            allow_multi_photo=is_allow_multi_photo
        )
        return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=303)
    except Exception as e:
        detail_msg = getattr(e, "detail", str(e))
        return templates.TemplateResponse(
            request=request,
            name="admin/event_form.html",
            context={
                "is_edit": False,
                "event": {
                    "slug": slug,
                    "title": title,
                    "description": description,
                    "allow_comments": bool(allow_comments),
                    "manager_only": bool(manager_only),
                    "hide_vote_counts": bool(hide_vote_counts),
                    "allow_multi_photo": bool(allow_multi_photo)
                },
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
async def edit_event_page(
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
    allow_comments: Optional[str] = Form(None),
    manager_only: Optional[str] = Form(None),
    hide_vote_counts: Optional[str] = Form(None),
    allow_multi_photo: Optional[str] = Form(None),
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
            is_active=bool(is_active),
            allow_comments=bool(allow_comments),
            manager_only=bool(manager_only),
            hide_vote_counts=bool(hide_vote_counts),
            allow_multi_photo=bool(allow_multi_photo)
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
async def delete_event_action(
    event_id: int,
    db: Session = Depends(get_db),
    auth_info: dict = Depends(require_manager_web)
):
    """이벤트 삭제 처리 (manager 권한 필요)"""
    event_service.delete_event(db, event_id)
    return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=303)
