import os
from pathlib import Path

# 기본 프로젝트 루트 디렉터리 경로
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Persistent Volume 및 데이터 디렉터리 경로 환경설정
# Docker 컨테이너 등에서 persistent volume을 마운트할 PATH 환경값 (예: /app/data)
raw_data_path = os.getenv("DATA_PATH", os.getenv("DATA_DIR", str(BASE_DIR / "data"))).strip()
DATA_DIR = Path(raw_data_path)
UPLOAD_DIR = DATA_DIR / "uploads"
COVERS_DIR = UPLOAD_DIR / "covers"
ITEMS_DIR = UPLOAD_DIR / "items"

# 필수 디렉터리 자동 생성
for d in [DATA_DIR, UPLOAD_DIR, COVERS_DIR, ITEMS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 환경 변수 및 설정
PROJECT_NAME = "VoteEvent"
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0")

# DEFAULT_PREFIX 설정 (기본값: /votes)
# 접두어가 / 로 시작하도록 하고, 끝의 / 는 제거
raw_prefix = os.getenv("DEFAULT_PREFIX", "/votes").strip()
if not raw_prefix.startswith("/"):
    raw_prefix = "/" + raw_prefix
DEFAULT_PREFIX = raw_prefix.rstrip("/")
if not DEFAULT_PREFIX:
    DEFAULT_PREFIX = "/votes"

# SQLite 데이터베이스 경로 (DB_PATH 환경변수 또는 DATABASE_URL 지원)
db_file_path = os.getenv("DB_PATH", str(DATA_DIR / "vote_event.db"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{db_file_path}")

# 이미지 처리 설정
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "1920"))
IMAGE_QUALITY = int(os.getenv("IMAGE_QUALITY", "85"))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
