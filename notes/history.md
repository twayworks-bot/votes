# 개발 요구사항 및 변경 이력 (history.md)

- **관리 원칙**: 개발 과정에서 수신된 모든 요구사항 요약 및 시스템 변경 사항을 시간 역순 또는 순차적으로 누적 기록합니다.

---

## [2026-10-05 21:06] 이벤트 서브패스(/votes/{eventName}) 접속 시 관리자 로그인 및 개설 링크의 /auth 누락 버그 수정

### 1. 요구사항 요약
- `/votes/{eventName}` (예: `/votes/bazaarposter`) 접근 시 네비게이션의 "관리자 로그인" 및 "새 이벤트 개설" 링크에서 `/auth` prefix가 유실되어 `/login`으로 이동하는 오류 해결.
- 원인: `event_view_router.py`에서 템플릿 context로 `auth_url`, `login_url` 미전달로 인한 Jinja2 빈 문자열 평가.
- 전역 템플릿 변수 보강 및 라우터별 세션 검증/인증 컨텍스트 연동.

### 2. 조치 내역
- [notes/req_202610052106.md](file:///C:/Dev/python/voteEvent/notes/req_202610052106.md) 작성
- [app/routers/event_view_router.py](file:///C:/Dev/python/voteEvent/app/routers/event_view_router.py)에 `verify_auth_session` 및 `auth_url`, `login_url`, `is_manager` 컨텍스트 주입
- Jinja2 템플릿 엔진에 `AUTH_URL`, `DEFAULT_PREFIX` 전역 변수 등록
- [app/templates/base.html](file:///C:/Dev/python/voteEvent/app/templates/base.html) 폴백 링크에서 `/auth/login` 경로 보장 방어 코드 적용
- [tests/test_vote_event.py](file:///C:/Dev/python/voteEvent/tests/test_vote_event.py)에 서브패스 링크 검증 테스트 추가
- [notes/result_202610052106.md](file:///C:/Dev/python/voteEvent/notes/result_202610052106.md) 작성

---

## [2026-10-05 19:29] Keycloak 인증 프록시 연동 및 매니저(manager flag=1) 권한 검증 구현

### 1. 요구사항 요약
- 이벤트 개설(생성) 및 수정, 삭제 기능에 대해 중앙 Keycloak 인증 프록시 세션 검증 필수 적용
- 검증 대상 Auth URL: `https://holyseeds.thewayworks.net/auth`
- 환경변수 `AUTH_URL` 추가
- `auth_session` 쿠키 기반으로 `GET {AUTH_URL}/api/verify-session?require_role=manager` 호출하여 `is_manager == True` 또는 `role_flag == "1"` 판별
- 비인가/미인증 시 `{AUTH_URL}/login`으로 안전한 리다이렉션 바운스 처리

### 2. 조치 내역
- [notes/req_202610051929.md](file:///C:/Dev/python/voteEvent/notes/req_202610051929.md) 작성
- [app/core/config.py](file:///C:/Dev/python/voteEvent/app/core/config.py)에 `AUTH_URL` 환경변수 추가
- [app/core/auth.py](file:///C:/Dev/python/voteEvent/app/core/auth.py) 인증 프록시 검증 모듈 개발
- [app/routers/admin_router.py](file:///C:/Dev/python/voteEvent/app/routers/admin_router.py)에 매니저 권한 검증 가드 적용
- 템플릿 네비게이션 및 대시보드에 로그인/로그아웃 및 사용자 권한 UI 반영
- [Dockerfile](file:///C:/Dev/python/voteEvent/Dockerfile) 및 [docker-compose.yml](file:///C:/Dev/python/voteEvent/docker-compose.yml)에 `AUTH_URL` 반영
- [notes/requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md)에 FR-10 누적
- [notes/result_202610051929.md](file:///C:/Dev/python/voteEvent/notes/result_202610051929.md) 작성

---

## [2026-10-05 19:05] 바자회 관련 텍스트 'baazar' -> 'bazaar' 오타 일괄 교정

### 1. 요구사항 요약
- 샘플 텍스트 및 기본 이벤트 슬러그/식별자 중 `baazar` 오타를 올바른 철자인 `bazaar`로 수정 요청 (`baazarposter` -> `bazaarposter`, `BaazarEvent` -> `BazaarEvent` 등).

### 2. 조치 내역
- [notes/req_202610051905.md](file:///C:/Dev/python/voteEvent/notes/req_202610051905.md) 작성
- 템플릿([app/templates/admin/event_form.html](file:///C:/Dev/python/voteEvent/app/templates/admin/event_form.html)) placeholder 오타 수정
- 시드 스크립트([scripts/seed_and_test.py](file:///C:/Dev/python/voteEvent/scripts/seed_and_test.py)) 이벤트 슬러그 및 텍스트 `bazaarposter` 교정 및 재실행
- 테스트 코드([tests/test_vote_event.py](file:///C:/Dev/python/voteEvent/tests/test_vote_event.py)) 검증 대상 슬러그 `bazaarposter` 갱신
- 문서([README.md](file:///C:/Dev/python/voteEvent/README.md), [GOAL.md](file:///C:/Dev/python/voteEvent/GOAL.md), [SPECIFICATION.md](file:///C:/Dev/python/voteEvent/notes/SPECIFICATION.md), [notes/requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md)) 내 오타 전면 수정
- [notes/result_202610051905.md](file:///C:/Dev/python/voteEvent/notes/result_202610051905.md) 작성

---

## [2026-10-05 12:30] Docker 컨테이너화, Persistent Volume 및 헬스체크 연동

### 1. 요구사항 요약
- **Dockerfile 생성**:
  - 기본 노출 포트 5000번 (`EXPOSE 5000`)
  - Persistent Volume 연동을 위한 DB/데이터 `DATA_PATH` 환경값 지원
  - `DEFAULT_PREFIX` 환경변수 연동 및 base URL 동적 반영
  - 컨테이너 헬스체크 지시어 추가 (`requests.get(f'http://localhost:5000{prefix}/api/status')`)
  - Gunicorn / Uvicorn 프로덕션 시작 커맨드 구성
- **헬스체크 엔드포인트 구현**: `{DEFAULT_PREFIX}/api/status` API 구현 및 `requests` 패키지 추가
- **보안 및 캐시 제외 설정**: `.gitignore` 및 `.dockerignore` 생성 (개인정보, 캐시, DB, 민감데이터 제외)
- **문서화 갱신**: `README.md` 도커 실행 및 볼륨 마운트 가이드 업데이트

### 2. 조치 내역
- [notes/req_202610051230.md](file:///C:/Dev/python/voteEvent/notes/req_202610051230.md) 작성
- [notes/requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md)에 FR-09 추가
- `app/core/config.py`에 `DATA_PATH` Persistent Volume 경로 지원 추가
- `app/routers/status_router.py` (또는 status 엔드포인트) 구현
- `Dockerfile`, `.dockerignore`, `.gitignore` 생성
- [README.md](file:///C:/Dev/python/voteEvent/README.md) 업데이트

---

## [2026-10-05 11:33] 개발 승인 및 첫 시드 이벤트/포트 요구사항 접수

### 1. 추가 요구사항 요약
- **개발 승인 완료**: 계획 검토 완료 및 본격적인 구현 시작 승인
- **서버 기본 포트**: 기본 실행 포트를 5000번(`PORT=5000`)으로 확정
- **첫 시드 이벤트 기획 및 테스트**:
  - 이벤트 등록: `baazarposter` - "바자회 홍보 포스터 자랑대회"
  - 참여자 항목 등록: "바자회홍보포스터 이미지"와 "제목" 생성 및 등록
  - 1920px 다운스케일링 및 투표, PIN 검증 종합 E2E 테스트 수행

### 2. 조치 내역
- [notes/req_202610051133.md](file:///C:/Dev/python/voteEvent/notes/req_202610051133.md) 작성
- [notes/requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md)에 포트 및 시드 이벤트 요구사항 누적 반영
- 전체 7단계(Phase 1~7) 구현 개시

---

## [2026-10-05 11:25] 초기 요구사항 수립 및 개발 계획 단계

### 1. 요구사항 요약
- **프로젝트명**: VoteEvent 참여형 투표 이벤트 웹 애플리케이션
- **관리자 기능**:
  - 기본 시작 basepath는 `DEFAULT_PREFIX` (예: `/votes`) 설정 기반으로 구동
  - 이벤트 등록, 리스트 조회, 수정, 삭제 기능 제공
  - 이벤트 대표 소개 텍스트 및 대표 소개 이미지 등록 관리
- **참여자/관람자 기능**:
  - 이벤트 등록 이름(예: `BaazarEvent`)을 subpath(예: `/votes/BaazarEvent`)로 직접 접근 가능한 친화적 URL UX
  - 참여자 본인이 직접 하위 항목(제목, 설명, 그림) 업로드
  - 업로드 시 개별 핀번호(PIN) 등록하여 동일 핀번호 입력 시에만 수정/삭제 허용
  - 하위 항목 리스트 간략보기(썸네일, 제목, 설명 요약)에서 바로 좋아요(투표) 가능
  - 하위 항목 자세히보기(상세 모달) 제공
- **미디어 처리**:
  - 원본 이미지 폭이 큰 경우 최대 1920픽셀로 자동 압축 변환 저장

### 2. 조치 및 산출물 내역
- [GOAL.md](file:///C:/Dev/python/voteEvent/GOAL.md): 프로젝트 구현 목적 및 핵심 목표 정의
- [notes/requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md): 기능적/비기능적 요구사항 상세 해석 및 추적 매트릭스 수립
- [notes/SPECIFICATION.md](file:///C:/Dev/python/voteEvent/notes/SPECIFICATION.md): FastAPI + Jinja2 + SQLite + Pillow 기반 아키텍처, 패키지 트리, API 엔드포인트 및 DB 모델 설계
- [notes/plan_202610051125.md](file:///C:/Dev/python/voteEvent/notes/plan_202610051125.md): MVP 범위 확정 및 7단계 상세 실행 계획 수립
- [notes/req_202610051125.md](file:///C:/Dev/python/voteEvent/notes/req_202610051125.md): 사용자 원본 요청문 및 상세 해석본 아카이빙
- [notes/result_202610051125.md](file:///C:/Dev/python/voteEvent/notes/result_202610051125.md): 요구사항 분석 및 계획 수립 산출물 생성 보고서 작성
