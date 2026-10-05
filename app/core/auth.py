import logging
import urllib.parse
from typing import Optional, Dict, Any
import requests
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from app.core.config import AUTH_URL

logger = logging.getLogger(__name__)


class AdminAuthRedirectException(Exception):
    """관리자 권한 미달 또는 비로그인 시 Keycloak 로그인 페이지로 리다이렉트하기 위한 예외"""
    def __init__(self, redirect_url: str):
        self.redirect_url = redirect_url


def build_login_url(redirect_url: str, error: Optional[str] = None, require_role: str = "manager") -> str:
    """Keycloak 프록시 로그인 게이트웨이 URL 생성"""
    params = {
        "redirect": redirect_url,
        "require_role": require_role,
    }
    if error:
        params["error"] = error
    return f"{AUTH_URL}/login?{urllib.parse.urlencode(params)}"


def build_logout_url(redirect_url: str) -> str:
    """Keycloak 프록시 로그아웃 URL 생성"""
    return f"{AUTH_URL}/logout?{urllib.parse.urlencode({'redirect': redirect_url})}"


def verify_auth_session(request: Request, require_role: str = "manager") -> Dict[str, Any]:
    """
    Keycloak 프록시 세션 검증 API (GET {AUTH_URL}/api/verify-session)를 호출하여
    현재 요청자의 로그인 상태 및 manager 권한(flag=1 이상) 여부를 판별합니다.
    """
    cookie_session = request.cookies.get("auth_session")
    query_session = request.query_params.get("session_id")
    session_id = cookie_session or query_session

    if not session_id:
        return {
            "valid": False,
            "is_manager": False,
            "user": None,
            "roles": [],
            "has_required_role": False,
            "error": "세션 쿠키(auth_session)가 존재하지 않습니다."
        }

    verify_endpoint = f"{AUTH_URL}/api/verify-session"
    params = {"require_role": require_role}
    if query_session:
        params["session_id"] = query_session

    cookies = {}
    if cookie_session:
        cookies["auth_session"] = cookie_session

    headers = {}
    if cookie_session:
        headers["Cookie"] = f"auth_session={cookie_session}"

    try:
        resp = requests.get(
            verify_endpoint,
            params=params,
            cookies=cookies,
            headers=headers,
            timeout=3.0
        )
        if resp.status_code == 200:
            data = resp.json()
            # manager flag=1 이상 또는 is_manager: True 또는 roles 에 manager 포함 여부
            role_flag = str(data.get("role_flag", "")).strip()
            roles = data.get("roles", [])
            if isinstance(roles, str):
                roles = [roles]

            is_mgr = bool(
                data.get("is_manager") is True
                or data.get("has_required_role") is True
                or role_flag in ("1", "2")
                or ("manager" in roles)
                or ("super" in roles)
            )
            data["is_manager"] = is_mgr
            return data
        else:
            return {
                "valid": False,
                "is_manager": False,
                "user": None,
                "roles": [],
                "has_required_role": False,
                "error": f"인증 서버 응답 오류 ({resp.status_code})"
            }
    except Exception as e:
        logger.warning(f"Keycloak 세션 검증 요청 실패 ({verify_endpoint}): {e}")
        return {
            "valid": False,
            "is_manager": False,
            "user": None,
            "roles": [],
            "has_required_role": False,
            "error": f"인증 프록시 통신 오류: {str(e)}"
        }


def require_manager_web(request: Request) -> Dict[str, Any]:
    """
    관리자 웹 화면용 FastAPI 의존성.
    manager flag=1 이상이 아닌 경우 Keycloak 공통 로그인 화면으로 303 Redirect합니다.
    """
    auth_info = verify_auth_session(request, require_role="manager")
    if not auth_info.get("is_manager"):
        # 사용자가 원래 요청했던 전체 절대/상대 URL
        current_url = str(request.url)
        login_url = build_login_url(
            redirect_url=current_url,
            error="관리자(Manager) 권한이 필요한 페이지입니다.",
            require_role="manager"
        )
        raise AdminAuthRedirectException(redirect_url=login_url)
    return auth_info


def require_manager_api(request: Request) -> Dict[str, Any]:
    """
    관리자 API용 FastAPI 의존성.
    manager flag=1 이상이 아닌 경우 403 Forbidden 예외를 발생시킵니다.
    """
    auth_info = verify_auth_session(request, require_role="manager")
    if not auth_info.get("is_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자(Manager) 권한이 필요합니다."
        )
    return auth_info
