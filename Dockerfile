# ==============================================================
# VoteEvent Dockerfile
# - 경량 Python 3.11-slim 베이스 이미지
# - Persistent Volume 연동: DATA_PATH=/app/data
# - 기본 노출 포트: 5000
# - Base URL Prefix 연동: DEFAULT_PREFIX=/votes
# - 컨테이너 헬스체크 및 프로덕션 ASGI/WSGI 실행
# ==============================================================

FROM python:3.11-slim

# 파이썬 표준 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=5000 \
    HOST=0.0.0.0

# 1. Persistent Volume을 연동하기 위한 PATH 환경값 설정
#    - SQLite DB 및 업로드 이미지가 보존될 디렉터리 경로
ENV DATA_PATH=/app/data

# 2. docker 컨테이너의 DEFAULT_PREFIX 환경세팅 값 (기본 base URL: /votes)
ENV DEFAULT_PREFIX=/votes

# 작업 디렉터리 설정
WORKDIR /app

# 시스템 빌드 의존성 및 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존 패키지 복사 및 설치
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스코드 복사
COPY . /app/

# 영구 볼륨 마운트 디렉터리 생성 및 권한 설정
RUN mkdir -p /app/data/uploads/covers /app/data/uploads/items

# Database 및 업로드 미디어용 Persistent Volume 선언
VOLUME ["/app/data"]

# 3. 노출 포트 5000번 설정
EXPOSE 5000

# 4. 컨테이너 헬스체크 정의 (요청한 사양에 맞춘 Prefix 경로 연동)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python -c "import os, requests; prefix = os.getenv('DEFAULT_PREFIX', ''); requests.get(f'http://localhost:5000{prefix}/api/status')"

# 5. 시작 CMD (Gunicorn 운영서버 또는 Uvicorn 중 선택)
# Gunicorn 운영서버로 기동 (요청한 사양에 맞춘 최적화 워커 및 디버깅 로그 옵션)
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:5000", "--workers", "2", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "main:app"]

# 대안: Uvicorn 직접 실행 시 아래 커맨드로 교체 가능
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
