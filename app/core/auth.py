import logging
import urllib.parse
from typing import Optional, Dict, Any
import os
import time
import json
import base64
import hmac
import hashlib
import requests
import httpx
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from app.core.config import AUTH_URL, AUTH_VERIFY_URL

logger = logging.getLogger(__name__)

# 로컬 세션 동기화용 HMAC 시크릿 키
LOCAL_AUTH_SECRET = os.getenv("SECRET_KEY", "vote-event-local-secret-key-2026")


def create_local_manager_token(user_data: Optional[Dict[str, Any]] = None, ttl: int = 86400) -> str:
    """
    웹 스크립트에서 원격 Keycloak 검증 완료 후 전달된 정보를 바탕으로
    로컬호스트(localhost)에서 신뢰할 수 있는 서명된 관리자 토큰을 생성합니다.
    """
    payload = {
        "user": user_data or {},
        "is_manager": True,
        "exp": int(time.time()) + ttl
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    b64_payload = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
    sig = hmac.new(LOCAL_AUTH_SECRET.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
    return f"localmgr.{b64_payload}.{sig}"


def verify_local_manager_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    서명된 로컬 관리자 토큰의 위변조 및 만료 여부를 검증합니다.
    """
    if not token or not isinstance(token, str) or not token.startswith("localmgr."):
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        _, b64_payload, sig = parts
        expected_sig = hmac.new(LOCAL_AUTH_SECRET.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # base64 패딩 복원
        padded = b64_payload + '=' * (-len(b64_payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if data.get("exp", 0) < time.time():
            return None
        if data.get("is_manager"):
            return data
    except Exception as e:
        logger.debug(f"Local token validation failed: {e}")
        return None
    return None


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


def extract_auth_session(request: Request) -> Optional[str]:
    """
    Request의 쿠키, 쿼리 파라미터, 헤더에서 세션 토큰을 안전하게 추출합니다.
    로컬 환경(localhost)에서 도메인 간 쿠키가 전달되지 않아 쿼리 파라미터로 전달되는 경우도 지원합니다.
    """
    # 1. 브라우저 세션 쿠키
    cookie_token = (
        request.cookies.get("local_manager_token")
        or request.cookies.get("auth_session")
        or request.cookies.get("session_id")
    )
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    # 2. 쿼리 파라미터 (로컬 로그인 리다이렉트 연동)
    query_token = (
        request.query_params.get("local_manager_token")
        or request.query_params.get("session_id")
        or request.query_params.get("auth_session")
    )
    if query_token and query_token.strip():
        return query_token.strip()

    # 3. HTTP Authorization 헤더 또는 X-Session-Id
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    header_token = (
        request.headers.get("X-Local-Manager-Token")
        or request.headers.get("X-Session-Id")
        or request.headers.get("X-Auth-Session")
    )
    if header_token and header_token.strip():
        return header_token.strip()

    return None


async def verify_admin_session(auth_session: str) -> bool:
    """
    Validate user credentials and check for manager status using Keycloak API Proxy.
    Dockerfile에 정의된 환경변수(AUTH_URL) 및 AUTH_VERIFY_URL을 기반으로 검증하며,
    웹 스크립트에서 동기화된 로컬 관리자 토큰(local_manager_token)도 우선 검증합니다.
    """
    if not auth_session:
        return False

    # 1. 로컬에 발급된 서명 토큰 우선 검증 (로컬호스트 브릿지)
    local_data = verify_local_manager_token(auth_session)
    if local_data and local_data.get("is_manager"):
        return True

    # 2. 원격 Keycloak 세션 비동기 검증
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                AUTH_VERIFY_URL,
                params={"session_id": auth_session},
                timeout=4.0
            )
            if response.status_code == 200:
                result = response.json()
                is_mgr = bool(
                    result.get("valid") is True
                    and (
                        result.get("is_manager") is True
                        or result.get("is_super") is True
                        or str(result.get("role_flag", "")).strip() in ("1", "2")
                        or ("manager" in result.get("roles", []))
                        or ("super" in result.get("roles", []))
                    )
                )
                return is_mgr
    except Exception as e:
        logger.error(f"[Auth Error] Failed to verify Keycloak session: {e}")
        print(f"[Auth Error] Failed to verify Keycloak session: {e}")
    return False


def verify_auth_session(request: Request, require_role: str = "manager") -> Dict[str, Any]:
    """
    Keycloak 프록시 세션 검증 API (GET {AUTH_VERIFY_URL})를 호출하여
    현재 요청자의 로그인 상태 및 manager 권한(flag=1 이상) 여부를 판별합니다.
    웹 스크립트에서 동기화된 로컬 토큰이 있을 경우 즉시 관리자 정보를 반환합니다.
    """
    session_id = extract_auth_session(request)

    if not session_id:
        return {
            "valid": False,
            "is_manager": False,
            "user": None,
            "roles": [],
            "has_required_role": False,
            "error": "세션 식별자(auth_session)가 존재하지 않습니다."
        }

    # 1. 로컬 서명 토큰 우선 검증
    local_data = verify_local_manager_token(session_id)
    if local_data and local_data.get("is_manager"):
        return {
            "valid": True,
            "is_manager": True,
            "user": local_data.get("user") or {"username": "admin", "name": "관리자"},
            "roles": ["user", "manager", "admin"],
            "has_required_role": True,
            "source": "local_sync"
        }

    params = {
        "session_id": session_id,
        "require_role": require_role
    }
    cookies = {"auth_session": session_id}
    headers = {"Cookie": f"auth_session={session_id}"}

    try:
        resp = requests.get(
            AUTH_VERIFY_URL,
            params=params,
            cookies=cookies,
            headers=headers,
            timeout=4.0
        )
        if resp.status_code == 200:
            data = resp.json()
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
        logger.warning(f"[Auth Error] Keycloak 세션 검증 요청 실패 ({AUTH_VERIFY_URL}): {e}")
        print(f"[Auth Error] Failed to verify Keycloak session: {e}")
        return {
            "valid": False,
            "is_manager": False,
            "user": None,
            "roles": [],
            "has_required_role": False,
            "error": f"인증 프록시 통신 오류: {str(e)}"
        }


async def verify_auth_session_async(request: Request, require_role: str = "manager") -> Dict[str, Any]:
    """비동기 Keycloak 세션 검증 (httpx.AsyncClient 사용)"""
    session_id = extract_auth_session(request)

    if not session_id:
        return {
            "valid": False,
            "is_manager": False,
            "user": None,
            "roles": [],
            "has_required_role": False,
            "error": "세션 식별자(auth_session)가 존재하지 않습니다."
        }

    # 1. 로컬 서명 토큰 우선 검증
    local_data = verify_local_manager_token(session_id)
    if local_data and local_data.get("is_manager"):
        return {
            "valid": True,
            "is_manager": True,
            "user": local_data.get("user") or {"username": "admin", "name": "관리자"},
            "roles": ["user", "manager", "admin"],
            "has_required_role": True,
            "source": "local_sync"
        }

    params = {
        "session_id": session_id,
        "require_role": require_role
    }
    cookies = {"auth_session": session_id}
    headers = {"Cookie": f"auth_session={session_id}"}

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                AUTH_VERIFY_URL,
                params=params,
                cookies=cookies,
                headers=headers
            )
        if resp.status_code == 200:
            data = resp.json()
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
        logger.warning(f"[Auth Error] Keycloak 세션 검증 요청 실패 ({AUTH_VERIFY_URL}): {e}")
        print(f"[Auth Error] Failed to verify Keycloak session: {e}")
        return {
            "valid": False,
            "is_manager": False,
            "user": None,
            "roles": [],
            "has_required_role": False,
            "error": f"인증 프록시 통신 오류: {str(e)}"
        }


async def require_manager_web(request: Request) -> Dict[str, Any]:
    """
    관리자 웹 화면용 FastAPI 의존성.
    manager flag=1 이상이 아닌 경우 Keycloak 공통 로그인 화면으로 303 Redirect하되,
    무한 루프 방지(Loop Breaker) 가드를 적용합니다.
    """
    auth_session = extract_auth_session(request)
    is_admin = await verify_admin_session(auth_session)

    # 1. verify_admin_session 성공 시 관리자 통과
    if is_admin:
        auth_info = verify_auth_session(request, require_role="manager")
        auth_info["is_manager"] = True
        auth_info["is_admin"] = True
        return auth_info

    # 2. 동기 verify_auth_session 백업 확인
    auth_info = verify_auth_session(request, require_role="manager")
    if auth_info.get("is_manager"):
        return auth_info

    # 3. 관리자 검증 실패 시 분기:
    # 3-1. 무한 루프 방지: 이미 로그인 리다이렉트를 시도했음에도 인증되지 않은 경우 (auth_attempted=1)
    if request.query_params.get("auth_attempted") or request.query_params.get("error"):
        logger.warning(f"[Auth Loop Prevented] Redirect loop broken for {request.url}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자(Manager) 권한이 확인되지 않았습니다. 원격 계정의 관리자 권한을 확인해주세요."
        )

    # 3-2. 첫 시도 시 Keycloak 로그인 페이지로 303 리다이렉트 (루프 방지용 auth_attempted=1 파라미터 부착)
    current_url = str(request.url)
    sep = "&" if "?" in current_url else "?"
    loop_safe_target = f"{current_url}{sep}auth_attempted=1"
    login_url = build_login_url(
        redirect_url=loop_safe_target,
        error="관리자(Manager) 권한이 필요한 페이지입니다.",
        require_role="manager"
    )
    raise AdminAuthRedirectException(redirect_url=login_url)


async def require_manager_api(request: Request) -> Dict[str, Any]:
    """
    관리자 API용 FastAPI 의존성.
    manager flag=1 이상이 아닌 경우 403 Forbidden 예외를 발생시킵니다.
    """
    auth_session = extract_auth_session(request)
    is_admin = await verify_admin_session(auth_session)
    if is_admin:
        auth_info = verify_auth_session(request, require_role="manager")
        auth_info["is_manager"] = True
        return auth_info

    auth_info = verify_auth_session(request, require_role="manager")
    if not auth_info.get("is_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자(Manager) 권한이 필요합니다."
        )
    return auth_info
