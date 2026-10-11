# 요구사항 정의서 (requirements.md)

- **문서 버전**: v1.6.0
- **최초 작성일**: 2026-10-05 11:25
- **최근 수정일**: 2026-10-11 22:56
- **관리 원칙**: 모든 신규 요구사항 및 변경사항은 본 문서에 누적(Append/Update)하여 기록 관리함.

---

## 1. 개요 및 목적
본 문서는 [GOAL.md](file:///C:/Dev/python/voteEvent/GOAL.md)에 수립된 목적과 목표를 바탕으로, 사용자의 요구사항을 실제 소프트웨어 개발을 위한 상세 기능적/비기능적 요구사항으로 명확히 정의하고 해석한 요구사항 명세서입니다.

---

## 2. 사용자 원본 요구사항 분석 및 매핑

| 번호 | 사용자 요구사항 요약 | 해석 및 구현 방향 |
| :---: | :--- | :--- |
| **U-1** | 관리자 시작 basepath는 DEFAULT_PREFIX(기본 `/votes`)로 시작하고 이벤트 등록, 리스트, 수정, 삭제 기능 제공 | 환경변수/설정 기반 Prefix 라우팅 구조 구현. `/votes` 경로에서 이벤트 관리 UI 제공 |
| **U-2** | 참여자/관람자는 등록된 이벤트 이름(예: `BazaarEvent`)을 subpath(예: `/votes/BazaarEvent`)로 직접 접근하여 간편 접근 UX 제공 | 이벤트 식별자(Slug/Name)를 URL Path Parameter로 매핑하는 전용 랜딩 페이지 라우터 구현 |
| **U-3** | 이벤트 하위 항목으로 제목, 설명, 그림 업로드 기능 제공 | 멀티파트 폼 데이터 처리 및 파일 스토리지 저장 파이프라인 구현 |
| **U-4** | 하위 항목 등록 시 개별 핀번호(PIN) 등록, 동일 핀번호에 한해 수정/삭제 가능 | 항목별 PIN 해시 저장 및 수정/삭제 요청 시 PIN 대조 인증 로직 구축 |
| **U-5** | 하위 항목 리스트 간략보기(제목, 설명 일부, 작은 이미지)에서 바로 투표 가능 | 비동기 투표 API(AJAX/Fetch) 연동 및 리스트 카드 뷰에 즉시 투표 버튼 제공 |
| **U-6** | 하위 항목 자세히 보기 기능 제공 | 모달 팝업 또는 상세 페이지에서 원본 비율 이미지, 전체 본문, 투표, 수정/삭제 폼 제공 |
| **U-7** | 이미지 업로드 시 원본 이미지가 큰 경우 폭 최대 1920px로 압축변환하여 저장 | Pillow 라이브러리를 활용하여 가로 폭 > 1920px 이미지 비율 유지 축소 및 압축 저장 |
| **U-8** | 서버 실행 기본 포트로 5000번 포트(`PORT=5000`) 사용 | 환경설정 기본값 `PORT = 5000` 지정 및 서버 구동 시 5000번 포트 바인딩 |
| **U-9** | 첫 이벤트 `bazaarposter` ("바자회 홍보 포스터 자랑대회") 등록 및 참여자 포스터 이미지/제목 등록 기획 및 테스트 | 시드 데이터 자동 초기화 및 1920px 초과 이미지 리사이즈를 포함한 E2E 등록/투표 테스트 스크립트 구축 |
| **U-10** | Dockerfile 생성 및 5000번 포트 노출 (`EXPOSE 5000`) | Python 경량 베이스 이미지 기반 컨테이너 빌드 파일 작성 및 5000번 포트 노출 |
| **U-11** | DB 파일 persistent volume 연동을 위한 PATH 환경값 설정 | `DATA_PATH` (또는 `DATA_DIR`) 환경변수 지원 및 볼륨 마운트 연동 |
| **U-12** | docker DEFAULT_PREFIX 환경변수 연동 및 base URL 작동 | 컨테이너 환경변수 `DEFAULT_PREFIX` (기본 `/votes`)에 따라 앱 전체 라우팅 및 헬스체크 연동 |
| **U-13** | 컨테이너 헬스체크 정의 (`requests.get(f'http://localhost:5000{prefix}/api/status')`) | `HEALTHCHECK` 지시어 등록, `{DEFAULT_PREFIX}/api/status` API 구현 및 `requests` 패키지 추가 |
| **U-14** | `.gitignore` 및 `.dockerignore` 개인정보/캐시/민감데이터 배제 목록 작성 | Git 및 Docker 빌드 컨텍스트에서 DB, 이미지, 임베디드 시크릿, 캐시 철저 제외 |
| **U-15** | "새 이벤트 개설" 및 "수정/삭제" 기능에 대한 Keycloak 인증 검증 (manager flag=1 이상) | `AUTH_URL` 환경변수 추가, `auth_session` 쿠키 기반 `verify-session?require_role=manager` 호출 및 권한 가드 적용 |
| **U-16** | 서브패스(`/votes/{eventName}`) 이동 시 "관리자 로그인", "새 이벤트 개설" 버튼 링크의 `/auth` prefix 보존 | `event_view_router.py` 및 전역 템플릿 환경에 `AUTH_URL`, `login_url`, `is_manager` 컨텍스트 주입 및 폴백 보강 |
| **U-17** | 투표 이벤트 종료 시 하위 항목 생성 및 선호도 투표 진행 차단 (버튼 disable/숨김 및 API 400 차단) | `is_active=False` 이벤트에 대해 프론트엔드 버튼 비활성화 및 백엔드 400 예외 차단 로직 구현 |
| **U-18** | 종료된 이벤트에 등록된 항목 수정 불가 | 종료된 이벤트의 하위 항목 수정 요청 시 400 차단 및 UI disabled 처리 |
| **U-19** | 종료된 이벤트의 하위 항목 "삭제하기" 버튼 disable 및 삭제 불가 | 종료된 이벤트의 하위 항목 삭제 요청 시 400 차단 및 UI disabled 처리 |
| **U-20** | Keycloak API 프록시 비동기 세션 검증(`verify_admin_session`) 및 환경변수 `AUTH_URL` 연동 | 비동기 `httpx` 기반 세션 검증 함수 구현 및 Dockerfile 환경변수 `AUTH_URL` 참조 |
| **U-21** | "관리자만 연결(`manager_only`)" 및 "좋아요 횟수 숨기기(`hide_vote_counts`)" 옵션 추가 | 이벤트 옵션 컬럼 추가, 비인가자 403 차단 및 카드 뱃지 노출, 일반 사용자 득표수 0 마스킹 및 인기순 정렬 숨김 |
| **U-22** | 관리자 기능("새 이벤트 개설", "수정", "삭제") 호출 시 내부 사전 검증(`verify_admin_session`) 후 분기 처리 및 로컬 복귀 origin URL 처리 | 버튼 클릭 시 `/api/auth/status` 사전 검증 헬퍼(`handleManagerAction`) 연동 및 `window.location.origin` 기반 완전한 리다이렉션 URL 구성 |
| **U-23** | localhost redirection 무한 루프(303 See Other 핑퐁) 방지 가드 (Loop Breaker) 및 `require_manager_web` 비동기 통일 | `auth_attempted=1` 기반 Loop Breaker 가드 도입 및 `require_manager_web` 비동기 `verify_admin_session` 호출 일치 |
| **U-24** | Dockerfile 내부 환경변수 `AUTH_VERIFY_URL` 추가 선언 및 `config.py` 연동 | Dockerfile `ENV AUTH_VERIFY_URL=${AUTH_URL}/api/verify-session` 및 앱 설정 주입 |
| **U-25** | 모든 관리자 호출 버튼에 대한 일관된 사전 검증 분기 처리 적용 | 개설, 수정, 삭제, 로그인 버튼에 `handleManagerAction` 전면 바인딩 및 분기 처리 |
| **U-26** | 웹 스크립트 기반 원격 Keycloak 직접 검증(`verify-session`) 및 로컬 백엔드 세션 동기화(`sync-session`)로 403 Forbidden 해결 | 브라우저 쿠키 격리 극복을 위해 클라이언트 JS에서 원격 verify-session 호출 후 `/api/auth/sync-session` 동기화 및 403 자가 치유 브릿지 |

---

## 3. 기능적 요구사항 (Functional Requirements)

### FR-01: Base Path 및 라우팅 설정
- **FR-01-1**: 시스템은 설정 파일 또는 환경변수를 통해 `DEFAULT_PREFIX` (기본값: `/votes`)를 주입받아 모든 웹 라우트 및 API 라우트의 베이스 경로로 적용해야 한다.
- **FR-01-2**: 루트 접속(`/`) 시 자동으로 `DEFAULT_PREFIX`로 리다이렉트하거나 안내 페이지를 제공해야 한다.
- **FR-01-3**: 서브패스 정적 자원(`/votes/static/...`) 및 업로드 미디어(`/votes/uploads/...`) 경로가 prefix에 맞게 격리 서빙되어야 한다.
- **FR-01-4**: 서버의 기본 청취(Listen) 포트는 `5000`번으로 설정하며, 환경변수 `PORT`를 통해 재지정할 수 있어야 한다.

### FR-02: 이벤트 관리 (Admin)
- **FR-02-1 [이벤트 등록]**:
  - 이벤트 이름(Slug, 고유값, URL 경로로 사용될 영숫자/하이픈), 이벤트 제목(Title), 설명(Description), 대표 소개 이미지(Cover Image)를 입력받아 등록할 수 있어야 한다.
  - 이벤트 이름(Slug)은 중복을 허용하지 않으며, URL 안전 문자(a-z, A-Z, 0-9, -, _) 검증을 수행한다.
- **FR-02-2 [이벤트 목록 조회]**:
  - 생성된 모든 이벤트의 목록, 대표 이미지 썸네일, 등록일시, 참여 항목 수, 총 투표 수를 카드 형태로 조회할 수 있어야 한다.
- **FR-02-3 [이벤트 수정]**:
  - 이벤트 제목, 설명, 대표 이미지를 수정할 수 있어야 한다.
- **FR-02-4 [이벤트 삭제]**:
  - 이벤트를 삭제할 수 있으며, 삭제 시 해당 이벤트에 종속된 모든 하위 참여 항목과 업로드 이미지 파일이 연쇄(Cascade) 삭제되어야 한다.

### FR-03: 사용자 이벤트 랜딩 및 뷰 모드
- **FR-03-1 [이벤트 서브패스 접근]**:
  - 사용자가 `{DEFAULT_PREFIX}/{event_name}` (예: `/votes/BazaarEvent`)으로 브라우저 접근 시 해당 이벤트 전용 웹 페이지가 로딩되어야 한다.
  - 존재하지 않는 이벤트 이름 접근 시 친절한 404 안내 페이지를 제공해야 한다.
- **FR-03-2 [이벤트 헤더 정보]**:
  - 이벤트 대표 이미지, 이벤트 제목, 설명, 참여 항목 총 개수, 총 투표 수를 상단에 노출한다.
- **FR-03-3 [간략보기 (List / Grid Summary View)]**:
  - 각 하위 항목의 작은 이미지(썸네일), 제목, 줄바꿈/말줄임 처리된 설명 일부, 현재 획득 투표 수, "투표하기(좋아요)" 버튼, "자세히보기" 버튼을 제공한다.
  - 간략보기 화면에서 페이지 이동 없이 바로 투표(좋아요)를 클릭하여 즉시 카운트를 반영할 수 있어야 한다.
- **FR-03-4 [자세히보기 (Detail View)]**:
  - 모달 팝업 또는 상세 뷰를 통해 최적화된 고화질 이미지, 전체 본문 텍스트, 등록일시, 실시간 투표 수, 투표 버튼을 표시한다.
  - 하단에 "수정", "삭제" 액션 버튼을 배치한다.

### FR-04: 하위 참여 항목 등록 및 PIN 보안
- **FR-04-1 [항목 등록 인터페이스]**:
  - 이벤트 페이지 내 '참여하기(항목 등록)' 모달 또는 폼을 제공한다.
  - 필수 입력 필드: 제목(Title), 설명(Description), 이미지 파일(Image File), 핀번호(PIN).
- **FR-04-2 [핀번호(PIN) 규칙]**:
  - 핀번호는 4자리 이상의 숫자 또는 비밀번호 형태여야 한다.
  - 핀번호는 데이터베이스에 평문(Plaintext)으로 저장되지 않고 솔트(Salt)가 적용된 단방향 해시(SHA-256 또는 bcrypt)로 저장되어야 한다.

### FR-05: 하위 참여 항목 수정 및 삭제
- **FR-05-1 [수정 및 삭제 시 핀번호 검증]**:
  - 수정 또는 삭제 요청 시 팝업/모달을 통해 핀번호 입력을 요구한다.
  - 입력한 핀번호가 해시 검증을 통과하지 못하면 적절한 에러 메시지(401 Unauthorized / 403 Forbidden)를 반환하고 작업을 거부한다.
- **FR-05-2 [항목 수정]**:
  - 핀번호 일치 시 제목, 설명 수정이 가능하며, 이미지 교체 여부를 선택할 수 있다. (기존 이미지 유지 가능)
- **FR-05-3 [항목 삭제]**:
  - 핀번호 일치 시 해당 항목 데이터 및 연계된 로컬 저장소 이미지 파일을 안전하게 삭제 처리한다.

### FR-06: 투표 및 좋아요 (Favorite)
- **FR-06-1 [원클릭 투표]**:
  - 간략보기 및 자세히보기 모두에서 좋아요 하트/투표 버튼을 클릭하면 비동기 API 요청으로 투표 수가 1 증가한다.
- **FR-06-2 [중복 투표 방지 메커니즘]**:
  - 브라우저 로컬 스토리지(LocalStorage) 또는 세션/쿠키 기반으로 사용자가 이미 투표한 항목 ID를 저장하여 동일 브라우저에서의 무분별한 중복 투표를 1차 차단하고 UI 상태(투표 완료 표시)를 토글한다.
  - (선택/확장) 클라이언트 IP 해시 기반 로깅을 통해 비정상적인 반복 투표를 방어한다.

### FR-07: 이미지 처리 파이프라인 (Image Resizing & Optimization)
- **FR-07-1 [이미지 확장자 및 안전성 검사]**:
  - 허용 확장자: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`.
  - 허용되지 않은 파일 포맷 업로드 차단.
- **FR-07-2 [가로 폭 최대 1920px 리사이즈]**:
  - 원본 이미지의 가로 폭(Width)이 1920픽셀을 초과할 경우, 원본 가로/세로 비율(Aspect Ratio)을 유지하면서 폭을 정확히 1920px로 축소 변환한다.
  - 원본 가로 폭이 1920px 이하인 경우에는 원본 해상도를 유지하여 불필요한 업스케일링을 방지한다.
- **FR-07-3 [압축 및 저장 최적화]**:
  - EXIF 메타데이터 회전 정보(Orientation)를 감지하여 올바른 각도로 보정한 후 저장한다.
  - 최적의 압축률(Quality 85~90%)을 적용하여 용량을 최소화한다.
  - 파일명은 충돌 방지를 위해 UUID 또는 타임스탬프 기반의 난수 파일명으로 변환하여 저장한다.

### FR-08: 첫 시드 이벤트 및 참여자 포스터 등록 테스트
- **FR-08-1 [시드 이벤트 'bazaarposter']**:
  - 시스템 초기 구동 또는 시드 스크립트 실행 시 슬러그 `bazaarposter`, 제목 `바자회 홍보 포스터 자랑대회`, 설명 및 소개 이미지를 갖는 기본 이벤트를 자동 생성할 수 있어야 한다.
- **FR-08-2 [참여자 포스터 항목 등록 및 검증]**:
  - 참여자로서 "바자회홍보포스터 이미지"와 "제목"을 갖는 참여 항목을 생성하여 등록하는 과정을 기능 및 통합 테스트로 검증해야 한다.
  - 가로 폭 1920px을 초과하는 대형 테스트 포스터 이미지를 업로드하여 자동 다운스케일링 및 정상 저장 여부를 확인해야 한다.

### FR-09: Docker 컨테이너 배포 및 Persistent Volume / 헬스체크
- **FR-09-1 [Dockerfile 생성]**:
  - Python 경량 슬림 이미지를 기반으로 5000번 포트(`EXPOSE 5000`)를 노출하는 컨테이너 빌드 파일 작성.
- **FR-09-2 [Persistent Volume PATH 환경값 연동]**:
  - `DATA_PATH` (기본값: `/app/data`) 환경변수를 지원하여 SQLite 데이터베이스 파일과 업로드 이미지 미디어가 호스트 또는 외부 영구 볼륨에 격리 보존되도록 구성.
- **FR-09-3 [DEFAULT_PREFIX 컨테이너 주입]**:
  - 컨테이너 환경변수 `DEFAULT_PREFIX` (기본 `/votes`)를 통해 애플리케이션 base URL 및 라우팅 prefix를 동적으로 주입받아 동작.
- **FR-09-4 [컨테이너 헬스체크 엔드포인트]**:
  - `GET {DEFAULT_PREFIX}/api/status` 엔드포인트를 구현하여 서비스 정상 가동 상태(`{"status": "ok", ...}`)를 반환.
  - Dockerfile 내에 `HEALTHCHECK` 명령어를 정의하여 주기적인 무중단 헬스 상태 감시 수행.
- **FR-09-5 [시작 CMD 구성]**:
  - Gunicorn(Uvicorn 워커 연동) 또는 Uvicorn 프로덕션 모드로 5000번 포트 바인딩 및 구동.
- **FR-09-6 [무시 파일 관리 (.gitignore / .dockerignore)]**:
  - DB 파일, 업로드 미디어, `.env`, 파이썬 캐시, 가상환경 등 개인정보 및 민감데이터가 Git 저장소나 Docker 이미지 컨텍스트에 포함되지 않도록 완전 차단.

### FR-10: Keycloak 인증 프록시 연동 및 관리자 권한 제어
- **FR-10-1 [환경 변수 AUTH_URL 설정]**:
  - 기본 인증 프록시 URL 환경 변수 `AUTH_URL` (`https://holyseeds.thewayworks.net/auth`)을 지원하며, `.env`, Dockerfile, docker-compose 등에서 주입 가능하도록 구성.
- **FR-10-2 [세션 검증 함수 (verify_auth_session)]**:
  - 클라이언트의 `auth_session` 쿠키를 추출하여 `GET {AUTH_URL}/api/verify-session?require_role=manager` 호출.
  - 응답 JSON에서 `is_manager == True` 또는 `role_flag == "1"`(또는 "2" 관리자 레벨)을 판별하여 관리자 권한 확인.
  - 외부 인증 서버 오류 또는 타임아웃 발생 시 장애 격리 및 안전한 비인가(False) 반환 처리.
- **FR-10-3 [관리자 웹 라우트 보호 (303 Redirect)]**:
  - "새 이벤트 개설" 페이지 접근 및 개설 Form 제출(`POST`), 이벤트 "수정/삭제" 화면 및 액션 시 미인증/비매니저 사용자는 `{AUTH_URL}/login?error=...&redirect=...&require_role=manager` 로 리다이렉트(HTTP 303).
- **FR-10-4 [관리자 UI 요소 가시성 및 로그인 연동]**:
  - 공통 네비게이션 헤더에 로그인/로그아웃 및 현재 사용자/매니저 상태 표기.
  - 이벤트 목록 페이지에서 매니저 권한 여부에 따라 "새 이벤트 개설", "수정", "삭제" 버튼을 안전하게 제어하고 안내 메시지 제공.
- **FR-10-5 [이벤트 서브패스 및 전체 뷰의 인증 컨텍스트/프리픽스 보존]**:
  - `/votes/{eventName}`을 포함한 모든 템플릿 뷰에서 Jinja2 전역 변수 및 컨텍스트를 통해 `AUTH_URL`, `login_url`, `logout_url`, `is_manager`, `user`를 일관되게 제공하여, 링크 클릭 시 `/auth` 접두사가 누락되지 않고 올바른 인증 프록시 게이트웨이로 연결되도록 보장한다.

### FR-11: 이벤트 종료 상태 제어 및 불변성 보장
- **FR-11-1 [종료 시 하위 항목 생성 차단]**:
  - `is_active=False`로 설정된 이벤트에 대해 프론트엔드 참여 등록 버튼을 `disabled` 처리하고 자물쇠 아이콘을 표시한다.
  - 백엔드 `POST /api/items` API 호출 시 `400 Bad Request` ("종료된 이벤트에는 신규 항목을 등록할 수 없습니다.")를 반환하여 무단 생성을 차단한다.
- **FR-11-2 [종료 시 기존 항목 수정 및 삭제 차단]**:
  - 종료된 이벤트의 기존 참여 항목에 대해 상세 모달 내 "수정하기" 및 "삭제하기" 버튼을 `disabled` 처리한다.
  - 백엔드 `POST /api/items/{id}/update` 및 `POST /api/items/{id}/delete` API 호출 시 올바른 PIN을 입력하더라도 `400 Bad Request` ("종료된 이벤트의 항목은 수정/삭제할 수 없습니다.")를 반환하여 데이터 불변성을 보장한다.
- **FR-11-3 [종료 시 선호도 투표 차단]**:
  - 카드뷰, 모아보기, 상세 모달의 투표 버튼을 `disabled` 처리하고 "투표 마감"으로 표시한다.
  - 백엔드 `POST /api/items/{id}/vote` API 호출 시 `{"success": false, "message": "종료된 투표 이벤트입니다.", "vote_count": 0}`를 반환하여 득표수 증가를 차단한다.

### FR-12: 이벤트 보안 및 프라이버시 옵션 (manager_only, hide_vote_counts)
- **FR-12-1 [관리자만 연결 옵션 (manager_only)]**:
  - 이벤트 생성/수정 시 `manager_only` 체크박스 옵션을 제공한다.
  - 옵션 활성화 시 이벤트 목록 카드 및 서브패스 헤더에 "관리자만 접근" 방패 뱃지(`<i class="fa-solid fa-shield-halved"></i>`)를 표시한다.
  - 일반 사용자 또는 익명 방문자가 접근 시 403 Forbidden 전용 안내 페이지(`templates/event/403.html`)를 렌더링하고, 하위 항목 상세 조회/등록/투표 API 접근을 403으로 전면 차단한다.
  - 관리자 세션이 확인된 사용자에게만 정상 화면 및 기능을 제공한다.
- **FR-12-2 [좋아요 횟수 숨기기 옵션 (hide_vote_counts)]**:
  - 이벤트 생성/수정 시 `hide_vote_counts` 체크박스 옵션을 제공한다.
  - 옵션 활성화 시 이벤트 목록 카드에 "득표수 숨김" 뱃지를 노출한다.
  - 일반 사용자에게는 헤더 총 득표수를 "비공개"로 표시하고, 개별 항목 카드의 득표수 뱃지를 숨기며, 항목 상세 API 및 투표 API 응답 시 `vote_count: 0`으로 마스킹한다.
  - 일반 사용자의 화면에서 "인기 투표순" 정렬 옵션을 숨긴다.
  - 관리자(Manager) 로그인 상태에서는 실제 누적 득표수를 정상 조회 및 정렬할 수 있도록 한다.

### FR-13: Keycloak 비동기 검증, 클라이언트 사전 검증 및 무한 루프 방지
- **FR-13-1 [비동기 verify_admin_session 엔드포인트 연동]**:
  - `AUTH_VERIFY_URL` (`{AUTH_URL}/api/verify-session`)을 호출하여 `valid: True` 및 `is_manager: True`를 판별하는 비동기 함수 `verify_admin_session(auth_session)`을 구현한다.
  - 클라이언트가 현재 세션 상태를 사전 확인할 수 있는 `GET {DEFAULT_PREFIX}/api/auth/status` API를 제공한다.
- **FR-13-2 [클라이언트 사전 검증 헬퍼 (handleManagerAction)]**:
  - "새 이벤트 개설", "수정", "삭제", "관리자 로그인" 버튼 클릭 시 외부로 즉시 이동하지 않고 사전에 `/api/auth/status`를 호출하여 세션을 먼저 확인한다.
  - 관리자 세션이 유효하면 Keycloak 리다이렉트 없이 즉시 대상 URL로 이동하거나 콜백을 실행한다.
  - 미인증 시 `window.location.origin`을 포함한 완전한 절대 경로를 `redirect` 파라미터로 결합하여 Keycloak 로그인 화면으로 이동시켜 로컬호스트(`localhost`) 복귀를 보장한다.
- **FR-13-3 [무한 리다이렉션 방지 가드 (Loop Breaker)]**:
  - 첫 로그인 리다이렉트 시 `redirect` 파라미터에 `auth_attempted=1` 플래그를 부착한다.
  - Keycloak을 다녀왔음에도 세션이 없거나 관리자 권한이 부족한 경우, 더 이상 303 리다이렉트를 반복하지 않고 403 Forbidden 안내로 안전하게 중단하여 브라우저와 서버 간의 무한 루프(303 See Other 핑퐁)를 방지한다.
  - `require_manager_web` 및 관련 라우터 엔드포인트를 `async def`로 통일하여 비동기 검증의 일관성을 유지한다.

### FR-14: Dockerfile 환경변수 표준화 및 관리자 버튼 전면 사전 검증
- **FR-14-1 [컨테이너 환경변수 연동]**:
  - `Dockerfile`에 `ENV AUTH_VERIFY_URL=${AUTH_URL}/api/verify-session` 선언을 명시하고 `app/core/config.py`에서 최우선 참조한다.
- **FR-14-2 [관리자 액션 버튼 전면 바인딩]**:
  - 상단 내비게이션, 이벤트 목록 상단, 빈 상태 개설 버튼뿐만 아니라 각 카드의 "수정", "삭제", 비인증 "관리자 로그인" 버튼에 `handleManagerAction`을 전면 바인딩하여 단일 파이프라인으로 사전 세션 검증 후 안전하게 분기하도록 보장한다.

### FR-15: 웹 스크립트 기반 원격 Keycloak 세션 검증 및 동기화 브릿지
- **FR-15-1 [클라이언트 JS 원격 verify-session 호출]**:
  - 브라우저 스크립트(`base.html`)에서 직접 `AUTH_VERIFY_URL`(`https://holyseeds.thewayworks.net/auth/api/verify-session`)을 `credentials: 'include'`로 비동기 호출하여, 브라우저에 보관된 원격 쿠키를 통해 세션 및 관리자 여부를 직접 획득한다.
- **FR-15-2 [로컬 백엔드 세션 동기화 (sync-session)]**:
  - 클라이언트 스크립트가 획득한 관리자 정보를 로컬 백엔드(`POST /votes/api/auth/sync-session`)로 전달하여, `localhost` 도메인용 관리자 쿠키(`local_manager_token`, `auth_session`)를 즉각 발급받아 교차 도메인 쿠키 미전송 문제를 극복한다.
- **FR-15-3 [403 Forbidden 자가 치유(Self-Healing) 브릿지]**:
  - 브라우저 주소창 직접 진입 등으로 403 화면 노출 시, 화면 내 스크립트가 원격 세션을 백그라운드로 즉각 확인하여 관리자면 로컬 쿠키 동기화 후 본래 페이지로 자동 복구(`window.location.replace`)한다.

---

## 4. 비기능적 요구사항 (Non-Functional Requirements)

- **NFR-01 [사용자 경험(UX) 및 반응형 디자인]**:
  - 모바일, 태블릿, 데스크톱 등 다양한 디바이스 뷰포트에서 레이아웃이 깨지지 않도록 반응형 웹(Responsive Web) 디자인을 적용한다.
  - 페이지 전체 새로고침 없이 투표, 모달 열기/닫기, 비동기 처리가 부드럽게 이루어지는 인터랙션을 제공한다.
- **NFR-02 [보안성]**:
  - 사용자가 입력하는 핀번호는 단방향 암호화 해시로 저장하여 관리자라도 사용자의 핀번호 원문을 알 수 없도록 보호한다.
  - 파일 업로드 시 디렉터리 순회(Path Traversal) 공격 방지를 위해 파일명을 서버에서 재명명(Sanitization)한다.
- **NFR-03 [성능 및 리소스]**:
  - 대형 이미지 압축 처리를 통해 네트워크 전송량을 줄이고 페이지 렌더링 성능을 극대화한다.
  - 경량 임베디드 데이터베이스(SQLite)를 사용하여 별도의 복잡한 DB 서버 설치 없이 즉시 실행 및 테스트가 가능하도록 구성한다.
- **NFR-04 [설정 유연성 및 배포 용이성]**:
  - `DEFAULT_PREFIX` 환경변수 지원을 통해 리버스 프록시(Nginx 등) 하위 경로나 독립 서브도메인 어디서든 유연하게 동작할 수 있도록 설계한다.

---

## 5. 데이터 엔티티 요구사항

### 5.1 Event (투표 이벤트)
- `id`: 정수형 Primary Key (Auto Increment)
- `slug`: 문자열, 고유값(Unique), 인덱스 (URL subpath용, 예: `BazaarEvent`, `bazaarposter`)
- `title`: 문자열 (이벤트 타이틀)
- `description`: 텍스트 (이벤트 상세 설명)
- `cover_image`: 문자열 (이벤트 대표 이미지 저장 경로)
- `is_active`: 불리언 (기본값: True, 진행/종료 여부)
- `allow_comments`: 불리언 (기본값: False, 댓글 허용 여부)
- `manager_only`: 불리언 (기본값: False, 관리자 전용 접근 여부)
- `hide_vote_counts`: 불리언 (기본값: False, 좋아요 횟수 숨김 여부)
- `created_at`: 일시 (생성일시)
- `updated_at`: 일시 (수정일시)

### 5.2 EventItem (이벤트 하위 참여 항목)
- `id`: 정수형 Primary Key (Auto Increment)
- `event_id`: 외래키 (Event.id, On Delete Cascade)
- `title`: 문자열 (항목 제목)
- `description`: 텍스트 (항목 상세 설명)
- `image_path`: 문자열 (1920px 리사이즈된 이미지 파일 경로)
- `pin_hash`: 문자열 (단방향 암호화된 PIN 해시)
- `vote_count`: 정수형 (기본값: 0, 누적 투표/좋아요 수)
- `created_at`: 일시 (등록일시)
- `updated_at`: 일시 (수정일시)

### 5.3 VoteLog (투표 기록)
- `id`: 정수형 Primary Key (Auto Increment)
- `item_id`: 외래키 (EventItem.id, On Delete Cascade)
- `voter_identifier`: 문자열 (클라이언트 식별자: 세션ID 또는 IP 해시)
- `created_at`: 일시 (투표일시)

---

## 6. 요구사항 추적 매트릭스 (Traceability Matrix)

| 요구사항 ID | 기능 명칭 | 대응 컴포넌트/모듈 | 테스트 시나리오 ID |
| :---: | :--- | :--- | :---: |
| **FR-01** | Base Path & 포트 5000 | `core/config.py`, `main.py`, `run.py` | TC-ROUTE-01 |
| **FR-02** | 이벤트 관리 (CRUD) | `routers/admin_router.py`, `services/event_service.py` | TC-EVENT-01 |
| **FR-03** | 이벤트 랜딩 & 뷰 모드 | `routers/event_view_router.py`, `templates/event/detail.html` | TC-VIEW-01 |
| **FR-04** | 하위 항목 등록 및 PIN 암호화 | `routers/item_router.py`, `core/security.py` | TC-ITEM-01 |
| **FR-05** | PIN 검증 수정 및 삭제 | `routers/item_router.py`, `services/item_service.py` | TC-ITEM-02 |
| **FR-06** | 좋아요/투표 처리 | `routers/vote_router.py`, `static/js/vote.js` | TC-VOTE-01 |
| **FR-07** | 1920px 이미지 리사이징 | `services/image_service.py` | TC-IMG-01 |
| **FR-08** | 시드 이벤트 및 참여자 등록 테스트 | `scripts/seed_and_test.py` | TC-SEED-01 |
| **FR-09** | Docker 배포 & Persistent 볼륨/헬스체크 | `Dockerfile`, `config.py`, `routers/status_router.py` | TC-DOCKER-01 |
| **FR-10** | Keycloak 인증 프록시 연동 및 관리자 권한 제어 | `core/auth.py`, `routers/admin_router.py` | TC-AUTH-01 |
| **FR-11** | 이벤트 종료 상태 제어 및 불변성 보장 | `item_service.py`, `vote_service.py`, `detail.html` | TC-ENDED-01 |
| **FR-12** | 이벤트 보안 및 프라이버시 옵션 (manager_only, hide_votes) | `event_view_router.py`, `item_router.py`, `403.html` | TC-OPTS-01 |
| **FR-13** | Keycloak 비동기 검증, 사전 검증 및 무한 루프 방지 | `core/auth.py`, `base.html`, `admin_router.py` | TC-PREAUTH-01 |
| **FR-14** | Dockerfile 환경변수 표준화 및 관리자 버튼 전면 사전 검증 | `Dockerfile`, `config.py`, `event_list.html`, `base.html` | TC-PREAUTH-02 |
| **FR-15** | 웹 스크립트 기반 원격 Keycloak 세션 검증 및 동기화 브릿지 | `base.html`, `admin_router.py`, `auth.py`, `403.html` | TC-SYNC-01 |
