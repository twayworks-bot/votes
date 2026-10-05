from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
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

@app.exception_handler(AdminAuthRedirectException)
async def admin_auth_redirect_handler(request: Request, exc: AdminAuthRedirectException):
    return RedirectResponse(url=exc.redirect_url, status_code=303)

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

