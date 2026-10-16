import os
import re
from pathlib import Path

# 기본 프로젝트 루트 디렉터리 경로
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv_with_interpolation(env_path: Path) -> None:
    """
    .env 파일을 읽어 환경변수를 로드하고, ${VAR} 형태의 참조 변수를 치환합니다.
    이미 OS 환경변수로 명시적 주입된 값이 있다면 덮어쓰지 않고 유지합니다.
    """
    if not env_path.exists() or not env_path.is_file():
        return

    parsed_vars = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            parsed_vars[key] = val

        def _interpolate(value: str) -> str:
            def _replacer(match):
                var_name = match.group(1)
                return os.environ.get(var_name, parsed_vars.get(var_name, match.group(0)))
            return re.sub(r"\$\{([A-Za-z0-9_]+)\}", _replacer, value)

        for key, val in parsed_vars.items():
            resolved = _interpolate(val)
            parsed_vars[key] = resolved
            if key not in os.environ:
                os.environ[key] = resolved
            elif "${" in os.environ[key]:
                os.environ[key] = _interpolate(os.environ[key])
    except Exception:
        pass


# .env 파일 우선 로드
_load_dotenv_with_interpolation(BASE_DIR / ".env")

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

# Keycloak 인증 서버 설정 (.env 및 컨테이너 환경변수 AUTH_URL, AUTH_VERIFY_URL 참조)
AUTH_URL = os.getenv("AUTH_URL", "https://holyseeds.thewayworks.net/auth").strip().rstrip("/")
raw_verify_url = os.getenv("AUTH_VERIFY_URL", f"{AUTH_URL}/api/verify-session").strip()
AUTH_VERIFY_URL = raw_verify_url.replace("${AUTH_URL}", AUTH_URL)

# VDSTREAM 비디오 스트리밍 API 설정 (.env의 VDSTREAM_URL 및 하위호환 VDSTREAM_BASE_URL 지원)
VDSTREAM_URL = os.getenv(
    "VDSTREAM_URL",
    os.getenv("VDSTREAM_BASE_URL", "https://holyseeds.thewayworks.net/vdstream")
).strip().rstrip("/")
VDSTREAM_BASE_URL = VDSTREAM_URL
VDSTREAM_PIN = os.getenv("VDSTREAM_PIN", "1234").strip()

# FOTOSTREAM 다중 사진 -> 동영상 변환 및 HLS 스트리밍 API 설정 (.env의 FOTOSTREAM_URL 참조)
FOTOSTREAM_URL = os.getenv(
    "FOTOSTREAM_URL",
    os.getenv("FOTOSTREAM_BASE_URL", "https://holyseeds.thewayworks.net/fotostream")
).strip().rstrip("/")
FOTOSTREAM_BASE_URL = FOTOSTREAM_URL

