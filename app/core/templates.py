from fastapi.templating import Jinja2Templates
from app.core.config import BASE_DIR, DEFAULT_PREFIX, AUTH_URL

# 공통 Jinja2 템플릿 환경 객체
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

# 전역 템플릿 변수 등록 (모든 템플릿에서 기본 참조 가능)
templates.env.globals["default_prefix"] = DEFAULT_PREFIX
templates.env.globals["auth_url"] = AUTH_URL
templates.env.globals["AUTH_URL"] = AUTH_URL
