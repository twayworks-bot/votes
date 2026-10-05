from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import DEFAULT_PREFIX, PROJECT_NAME
from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/api/status")
def health_check(db: Session = Depends(get_db)):
    """
    컨테이너 및 애플리케이션 헬스체크 엔드포인트
    - URL: {DEFAULT_PREFIX}/api/status
    - Dockerfile HEALTHCHECK 및 로드밸런서 Liveness/Readiness 프로브용
    """
    db_ok = True
    try:
        # 데이터베이스 연결 상태 확인
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "app": PROJECT_NAME,
        "prefix": DEFAULT_PREFIX,
        "database": "connected" if db_ok else "error"
    }
