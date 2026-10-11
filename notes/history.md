# 개발 요구사항 및 변경 이력 (history.md)

- **관리 원칙**: 개발 과정에서 수신된 모든 요구사항 요약 및 시스템 변경 사항을 시간 역순 또는 순차적으로 누적 기록합니다.

---

## [2026-10-11 22:56] 웹 스크립트 기반 원격 세션 검증(verify-session) 및 로컬 백엔드 동기화(sync-session)를 통한 403 Forbidden 해결

### 1. 요구사항 요약
- **도메인 간 브라우저 쿠키 격리 및 403 Forbidden 원인 규명**:
  - `holyseeds.thewayworks.net`에 저장된 Keycloak 세션 쿠키가 `localhost` 도메인 요청 시 전송되지 않아, 파이썬 백엔드 검증 시 세션이 누락되어 `GET /votes/create?auth_attempted=1 403 Forbidden` 발생.
- **웹 스크립트(Client JS) 직접 검증 파이프라인 구축**:
  - 브라우저 스크립트에서 직접 `AUTH_VERIFY_URL`(`https://holyseeds.thewayworks.net/auth/api/verify-session`)을 `credentials: 'include'`로 호출하여 원격 도메인 쿠키를 실어 세션 검증 결과 수신.
- **로컬 백엔드 세션 동기화 API (`/api/auth/sync-session`) 구현**:
  - 웹 스크립트가 수신한 관리자 정보(`valid: true, is_manager: true, user: {...}`)를 로컬 백엔드로 전달.
  - 로컬 백엔드는 이를 검증하여 `localhost` 도메인용 관리자 쿠키(`local_manager_token`, `auth_session`)를 `Set-Cookie`로 발급.
  - 발급 후 `/votes/create` 진입 시 백엔드 검증이 100% 통과하여 403 에러 원천 해결.
- **자가 치유(Self-Healing) 브릿지 탑재**:
  - 403 페이지 도달 시에도 웹 스크립트가 원격 세션을 자동 확인하여 관리자 확인 시 즉시 동기화 후 자동 복구(`window.location.replace`).

### 2. 조치 내역
- [notes/req_202610112256.md](file:///C:/Dev/python/voteEvent/notes/req_202610112256.md) 작성
- [notes/plan_202610112256.md](file:///C:/Dev/python/voteEvent/notes/plan_202610112256.md) 작성
- [notes/result_202610112256.md](file:///C:/Dev/python/voteEvent/notes/result_202610112256.md) 작성
- [app/core/templates.py](file:///C:/Dev/python/voteEvent/app/core/templates.py)에 `auth_verify_url` 전역 템플릿 변수 추가
- [app/core/auth.py](file:///C:/Dev/python/voteEvent/app/core/auth.py)에 `create_local_manager_token`, `verify_local_manager_token` 구현 및 검증 연동
- [app/routers/admin_router.py](file:///C:/Dev/python/voteEvent/app/routers/admin_router.py)에 `POST /votes/api/auth/sync-session` 추가
- [app/templates/base.html](file:///C:/Dev/python/voteEvent/app/templates/base.html)에 `verifyAndSyncRemoteSession()` 및 `handleManagerAction()` 개선
- [app/templates/event/403.html](file:///C:/Dev/python/voteEvent/app/templates/event/403.html)에 자가 치유 스크립트 탑재
- [app/main.py](file:///C:/Dev/python/voteEvent/app/main.py)에 403 HTML 템플릿 예외 핸들러 연동 및 `TemplateResponse` 키워드 인자 순서 불일치 수정 (`TypeError: unhashable type: 'dict'` 500 오류 해결)
- [tests/test_vote_event.py](file:///C:/Dev/python/voteEvent/tests/test_vote_event.py)에 동기화 E2E 테스트 및 브라우저 HTML 403 렌더링 검증 추가 (전체 35개 테스트 전원 통과)

---

## [2026-10-11 22:43] Dockerfile AUTH_VERIFY_URL 환경변수 반영, 사전 세션 검증(verify_admin_session) 및 관리자 버튼 분기 제어

### 1. 요구사항 요약
- **Dockerfile 환경변수 선언 및 동기화**:
  - `ENV AUTH_URL=https://holyseeds.thewayworks.net/auth`
  - `ENV AUTH_VERIFY_URL=${AUTH_URL}/api/verify-session`
  - 애플리케이션 설정(`app/core/config.py`)에서 `AUTH_VERIFY_URL` 환경변수를 최우선 참조하도록 반영.
- **클라이언트 사전 세션 검증(Pre-verification) 절차 고도화**:
  - "새 이벤트 개설"을 비롯한 관리자 기능 호출 시, 원격 Keycloak으로 즉시 리다이렉트하지 않고 내부 시스템(`/votes/api/auth/status` -> `verify_admin_session`)을 먼저 비동기 호출.
  - 인증 세션이 검증된 상태(`is_manager: true`)이면 리다이렉션 없이 바로 대상 관리자 URL(`/votes/create` 등)로 직접 이동.
  - 미인증 상태인 경우에만 Keycloak 로그인 URL(`AUTH_URL + /login?redirect=...&require_role=manager`)로 이동하되, 로컬 개발 환경에서도 정상 복귀할 수 있도록 `window.location.origin`을 포함한 완전한 절대 URL을 전달.
- **관리자 호출 버튼 분기 처리 통일**:
  - 상단 네비게이션 "새 이벤트 개설" 버튼
  - 이벤트 목록 상단 및 빈 목록 "새 이벤트 개설" 버튼
  - 이벤트 카드별 "수정" 버튼
  - 이벤트 카드별 "삭제" 버튼
  - 비인증 상태의 "관리자 로그인" 버튼
  - 모든 관리자 호출 버튼에 `handleManagerAction`을 일관되게 바인딩하여 사전 검증 및 분기 처리 보장.

### 2. 조치 내역
- [notes/req_202610112243.md](file:///C:/Dev/python/voteEvent/notes/req_202610112243.md) 사용자 원본 요구사항 및 분석 기록 작성
- [notes/plan_202610112243.md](file:///C:/Dev/python/voteEvent/notes/plan_202610112243.md) MVP 정의 및 세부 개발 계획 수립
- [notes/result_202610112243.md](file:///C:/Dev/python/voteEvent/notes/result_202610112243.md) 산출물 생성 및 검증 결과서 작성
- [Dockerfile](file:///C:/Dev/python/voteEvent/Dockerfile)에 `ENV AUTH_VERIFY_URL=${AUTH_URL}/api/verify-session` 추가 반영
- [app/core/config.py](file:///C:/Dev/python/voteEvent/app/core/config.py)에 `AUTH_VERIFY_URL = os.getenv("AUTH_VERIFY_URL", ...)` 설정 추가
- [app/core/auth.py](file:///C:/Dev/python/voteEvent/app/core/auth.py)에 `verify_admin_session` 비동기 검증 및 Loop Breaker 가드 정밀화
- [app/routers/admin_router.py](file:///C:/Dev/python/voteEvent/app/routers/admin_router.py)에 `/votes/api/auth/status` 사전 검증 엔드포인트 연동
- [app/templates/base.html](file:///C:/Dev/python/voteEvent/app/templates/base.html)에 `handleManagerAction` 개선 (세션 토큰 동기화 및 `origin` 기반 리다이렉트)
- [app/templates/admin/event_list.html](file:///C:/Dev/python/voteEvent/app/templates/admin/event_list.html)의 모든 관리자 버튼에 `handleManagerAction` 전면 바인딩
- [tests/test_vote_event.py](file:///C:/Dev/python/voteEvent/tests/test_vote_event.py)에 신규 검증 테스트 보강 및 33개 테스트 전원 통과 확인

---

## [2026-10-11 22:27] MVP 정의, 종료 이벤트 제어, 관리자 전용/득표수 숨김 옵션, Keycloak 사전 검증 및 무한 루프 방지

### 1. 요구사항 요약
- **종료된 이벤트 불변성 보장**:
  - 투표 이벤트가 종료(`is_active=False`)되면 신규 항목 생성, 기존 항목 수정/삭제, 선호도 투표 전면 차단 (버튼 `disabled` 처리 및 백엔드 400 Bad Request).
- **Keycloak 비동기 세션 검증(`verify_admin_session`) 연동**:
  - `AUTH_VERIFY_URL`을 통해 Keycloak API 프록시에서 비동기로 관리자(`is_manager`) 권한을 검증하고, `Dockerfile` 환경변수 `AUTH_URL` 연동.
- **이벤트 옵션 기능 추가**:
  - "관리자만 연결(`manager_only`)": 일반/익명 사용자 403 Forbidden 안내 페이지 차단 및 이벤트 목록 카드에 방패 뱃지 노출.
  - "좋아요 횟수 숨기기(`hide_vote_counts`)": 일반 사용자 대상 총 득표수/카드 득표수 0 마스킹 및 인기순 정렬 숨김. 관리자는 정상 조회 가능.
- **클라이언트 사전 검증(`handleManagerAction`) 및 로컬 복귀 리다이렉션 개선**:
  - 관리자 액션 호출 시 외부로 바로 튕겨나가지 않고 내부 엔드포인트(`/api/auth/status`)를 먼저 조회하여 세션 유효 시 즉시 이동, 미인증 시 `window.location.origin`을 포함한 완전한 redirection URL로 Keycloak 호출.
  - "새 이벤트 개설", "수정", "삭제" 버튼에 일관 적용 및 페이지 로드 시 UI 백그라운드 동기화.
- **localhost redirection 무한 루프(303 See Other 핑퐁) 원인 분석 및 해결**:
  - 쿠키 도메인 격리 및 `require_manager_web` 검증 불일치 원인 분석.
  - `require_manager_web` 비동기화 및 `verify_admin_session` 호출 일치, `auth_attempted=1` 기반 Loop Breaker 가드 도입으로 무한 루프 원천 차단.
- **MVP 정의 및 개발 세부 계획 수립**:
  - 투표 플랫폼의 최소 기능 제품(MVP) 정의 및 단계별 세부 계획 수립.

### 2. 조치 내역
- [notes/req_202610112227.md](file:///C:/Dev/python/voteEvent/notes/req_202610112227.md) 원본 요구사항 기록
- [notes/plan_202610112227.md](file:///C:/Dev/python/voteEvent/notes/plan_202610112227.md) MVP 정의 및 세부 계획 수립
- [app/models/event.py](file:///C:/Dev/python/voteEvent/app/models/event.py)에 `manager_only`, `hide_vote_counts` 컬럼 추가
- [app/core/auth.py](file:///C:/Dev/python/voteEvent/app/core/auth.py)에 `verify_admin_session`, 비동기 `require_manager_web`, Loop Breaker 구현
- [app/routers/admin_router.py](file:///C:/Dev/python/voteEvent/app/routers/admin_router.py)에 `/api/auth/status` 추가 및 엔드포인트 비동기 통일
- [app/routers/event_view_router.py](file:///C:/Dev/python/voteEvent/app/routers/event_view_router.py), [item_router.py](file:///C:/Dev/python/voteEvent/app/routers/item_router.py), [vote_router.py](file:///C:/Dev/python/voteEvent/app/routers/vote_router.py)에 옵션별 접근 제어 및 마스킹 로직 적용
- [app/templates/base.html](file:///C:/Dev/python/voteEvent/app/templates/base.html), [admin/event_list.html](file:///C:/Dev/python/voteEvent/app/templates/admin/event_list.html)에 `handleManagerAction` 연동 및 상태 동기화 스크립트 적용
- [app/templates/event/403.html](file:///C:/Dev/python/voteEvent/app/templates/event/403.html) 전용 차단 안내 페이지 신규 제작
- [tests/test_vote_event.py](file:///C:/Dev/python/voteEvent/tests/test_vote_event.py)에 7종 신규 테스트 추가 (총 33개 테스트 100% 통과)
- [notes/result_202610112227.md](file:///C:/Dev/python/voteEvent/notes/result_202610112227.md) 산출물 생성 기록 작성
- [notes/requirement.md](file:///C:/Dev/python/voteEvent/notes/requirement.md)에 U-17 ~ U-23 및 FR-11 ~ FR-13 누적 갱신

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
