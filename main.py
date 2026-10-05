"""
VoteEvent 애플리케이션 진입점 (Docker 및 외부 ASGI 서버 호환용)
"""
from app.main import app

__all__ = ["app"]
