from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pathlib import Path

from app.core.config import DEFAULT_PREFIX, PROJECT_NAME, BASE_DIR, UPLOAD_DIR
from app.core.database import init_db
from app.core.auth import AdminAuthRedirectException
from app.routers import admin_router, event_view_router, item_router, vote_router, status_router
from fastapi import Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 DB 테이블 초기화
    init_db()
    yield


app = FastAPI(
    title=PROJECT_NAME,
    description="참여형 투표 이벤트 웹 플랫폼",
    lifespan=lifespan
)

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from app.core.templates import templates
from app.core.auth import AdminAuthRedirectException, build_login_url

@app.exception_handler(AdminAuthRedirectException)
async def admin_auth_redirect_handler(request: Request, exc: AdminAuthRedirectException):
    return RedirectResponse(url=exc.redirect_url, status_code=303)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    403 Forbidden 발생 시 브라우저 HTML 요청이면 친절한 안내 및 자동 복구 스크립트가 포함된
    403.html 템플릿을 렌더링하고, API 요청인 경우 JSON 응답을 반환합니다.
    """
    accept = request.headers.get("Accept", "")
    if exc.status_code == 403 and "text/html" in accept:
        current_url = str(request.url)
        clean_url = current_url.split("?")[0]
        login_url = build_login_url(redirect_url=clean_url, require_role="manager")
        return templates.TemplateResponse(
            request=request,
            name="event/403.html",
            context={
                "event": {"slug": ""},
                "login_url": login_url,
                "user": None,
                "detail": exc.detail
            },
            status_code=403
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.middleware("http")
async def local_auth_session_middleware(request: Request, call_next):
    """
    로컬 환경(localhost)에서 Keycloak 로그인 후 쿼리 파라미터(?session_id=... 또는 ?auth_session=...)로
    돌아왔을 때, 브라우저에 쿠키(auth_session)를 자동으로 심어주어 이후 요청에서도 로그인 세션이 유지되도록 합니다.
    """
    query_session = request.query_params.get("session_id") or request.query_params.get("auth_session")
    response = await call_next(request)
    if query_session and not request.cookies.get("auth_session"):
        response.set_cookie(
            key="auth_session",
            value=query_session.strip(),
            path="/",
            httponly=True,
            samesite="lax"
        )
    return response

# 1. 정적 파일 및 미디어 파일 마운트
static_dir = BASE_DIR / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount(f"{DEFAULT_PREFIX}/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount(f"{DEFAULT_PREFIX}/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 2. 루트 경로(/) 접속 시 기본 DEFAULT_PREFIX로 리다이렉트
@app.get("/")
def root_redirect():
    return RedirectResponse(url=f"{DEFAULT_PREFIX}/", status_code=302)

# 3. 라우터 등록
# 헬스체크 라우터 ({DEFAULT_PREFIX}/api/status 및 루트 /api/status 지원)
app.include_router(status_router.router, prefix=DEFAULT_PREFIX)
if DEFAULT_PREFIX and DEFAULT_PREFIX != "":
    app.include_router(status_router.router)

# API 라우터 (item_router, vote_router)
app.include_router(item_router.router, prefix=DEFAULT_PREFIX)
app.include_router(vote_router.router, prefix=DEFAULT_PREFIX)

# 관리자 라우터 (/votes, /votes/create, /votes/edit 등)
app.include_router(admin_router.router, prefix=DEFAULT_PREFIX)

# 퍼블릭 이벤트 뷰어 라우터 (/votes/{eventName})
# admin 라우트와 매칭되지 않는 subpath는 이벤트로 처리
app.include_router(event_view_router.router, prefix=DEFAULT_PREFIX)

