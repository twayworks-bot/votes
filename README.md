# VoteEvent - 참여형 투표 이벤트 웹 플랫폼

> 관리자가 투표 이벤트를 손쉽게 개설하고, 참가자가 자율적으로 작품(텍스트, 이미지)을 등록하며, 관람자가 좋아요(Favorite) 투표를 행사할 수 있는 참여형 웹 애플리케이션입니다.

---

## 🌟 주요 기능 및 특징

1. **유연한 Base Path 라우팅 (`DEFAULT_PREFIX`)**:
   - 기본 경로 `/votes`를 기준으로 관리자 및 이벤트 페이지 격리 서빙
   - 루트 경로(`/`) 접속 시 자동으로 `/votes`로 리다이렉트
2. **친화적인 Subpath 접속 UX**:
   - 참여자/관람자는 등록된 이벤트 이름(Slug)을 통해 `/votes/{eventName}` (예: `/votes/baazarposter`)으로 직접 접근
3. **참여자 하위 항목 등록 및 PIN 보안**:
   - 제목, 설명, 이미지 파일 업로드
   - 4자리 이상의 핀번호(PIN)를 등록받아 단방향 Salted Hash(PBKDF2/SHA-256)로 저장
   - 수정 및 삭제 시 동일 핀번호 검증 통과 시에만 처리
4. **듀얼 뷰 (Dual-View) & 원클릭 즉시 투표**:
   - **간략보기**: 작은 썸네일, 제목, 줄바꿈 말줄임 설명, "좋아요(투표)" 즉시 반영 버튼
   - **자세히보기 (모달)**: 고화질 원본비율 이미지, 전체 상세 본문, 실시간 득표수, 수정/삭제 진입점
   - 브라우저 로컬스토리지 및 세션 기반 중복 투표 방지
5. **대용량 이미지 1920px 다운스케일링 파이프라인**:
   - 업로드된 이미지 폭이 1920px을 초과할 경우 비율을 유지하며 폭 1920px로 리사이징 및 최적화(WebP/JPEG) 압축 저장
   - 스마트폰 사진의 회전 메타데이터(EXIF Orientation) 자동 보정
6. **Docker 컨테이너화 및 Persistent Volume 지원**:
   - 5000번 기본 포트 노출 (`EXPOSE 5000`)
   - `DATA_PATH` 환경변수를 통한 DB 및 업로드 미디어 영구 볼륨(Persistent Volume) 마운트 지원
   - 컨테이너 무중단 헬스체크 (`HEALTHCHECK`) 지원

---

## 🐳 Docker 컨테이너 실행 가이드

### 1. 환경변수 및 Persistent Volume 설정

| 환경변수 | 기본값 | 설명 |
| :--- | :---: | :--- |
| `DEFAULT_PREFIX` | `/votes` | 웹 애플리케이션의 기본 Base URL Prefix |
| `PORT` | `5000` | 컨테이너 내부 서비스 포트 |
| `DATA_PATH` | `/app/data` | SQLite DB 파일 및 업로드 이미지가 영구 보존될 Persistent Volume 경로 |
| `HOST` | `0.0.0.0` | 서버 바인딩 호스트 |

### 2. Docker 빌드 및 실행

#### 1) Docker 이미지 빌드
```bash
docker build -t vote-event:latest .
```

#### 2) Persistent Volume을 연동한 컨테이너 실행
호스트의 `$(pwd)/data` 디렉터리를 컨테이너의 `/app/data`로 마운트하여 컨테이너가 재시작되어도 DB와 업로드 파일이 영구 유지됩니다.

```bash
# Linux / macOS / PowerShell
docker run -d \
  --name vote_event \
  -p 5000:5000 \
  -v ${PWD}/data:/app/data \
  -e DEFAULT_PREFIX=/votes \
  -e DATA_PATH=/app/data \
  vote-event:latest
```

### 3. Docker Compose 사용 (권장)

`docker-compose.yml`을 통해 한 줄로 빌드 및 실행이 가능합니다:

```bash
docker compose up -d
```

### 4. 컨테이너 헬스체크 확인

Dockerfile에 정의된 헬스체크를 통해 컨테이너의 정상 동작 여부를 확인할 수 있습니다:
```bash
docker inspect --format='{{json .State.Health}}' vote_event
```
- **헬스체크 엔드포인트**: `GET http://localhost:5000{DEFAULT_PREFIX}/api/status`
- **응답 예시**: `{"status": "ok", "app": "VoteEvent", "prefix": "/votes", "database": "connected"}`

---

## 🚀 로컬 개발 환경 실행 가이드

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 첫 이벤트('baazarposter') 및 샘플 데이터 시드 생성
```bash
python scripts/seed_and_test.py
```

### 3. 로컬 서버 실행 (기본 포트: 5000)
```bash
python run.py
```

### 4. 웹 브라우저 접속
- **첫 이벤트 랜딩 페이지**: [http://localhost:5000/votes/baazarposter](http://localhost:5000/votes/baazarposter)
- **이벤트 관리자 대시보드**: [http://localhost:5000/votes](http://localhost:5000/votes)
- **새 이벤트 개설 페이지**: [http://localhost:5000/votes/create](http://localhost:5000/votes/create)
- **헬스체크 엔드포인트**: [http://localhost:5000/votes/api/status](http://localhost:5000/votes/api/status)

---

## 🧪 자동화 테스트 실행

```bash
pytest -v
```

---

## 🛡️ 보안 및 무시 파일 정책 (.gitignore / .dockerignore)

본 프로젝트는 보안 무결성 및 경량 컨테이너 이미지를 위해 민감 정보와 임시 파일들을 철저하게 격리합니다:
- **개인정보 및 인증값**: `.env`, `*.pem`, `*.key`, `secrets/`, `credentials/` 제외
- **데이터베이스 및 미디어**: `data/`, `*.db`, `*.sqlite`, `uploads/` 제외 (호스트/볼륨으로만 관리)
- **런타임 및 캐시 파일**: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage`, `.venv/` 제외

---

## 📁 주요 문서 링크

- [GOAL.md](file:///C:/Dev/python/voteEvent/GOAL.md): 프로젝트 구현 목적 및 목표 수립서
- [requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md): 기능적/비기능적 요구사항 명세서 (누적)
- [SPECIFICATION.md](file:///C:/Dev/python/voteEvent/notes/SPECIFICATION.md): 상세 개발 및 아키텍처 명세서
- [plan_202610051125.md](file:///C:/Dev/python/voteEvent/notes/plan_202610051125.md): MVP 정의 및 개발 실행 계획서
- [history.md](file:///C:/Dev/python/voteEvent/notes/history.md): 개발 요구사항 및 변경 이력
- [req_202610051230.md](file:///C:/Dev/python/voteEvent/notes/req_202610051230.md): Docker 요구사항 기록
- [result_202610051230.md](file:///C:/Dev/python/voteEvent/notes/result_202610051230.md): Docker 구현 및 검증 산출물 보고서
