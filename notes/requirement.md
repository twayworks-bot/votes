# 요구사항 정의서 (requirements.md)

- **문서 버전**: v1.3.0
- **최초 작성일**: 2026-10-05 11:25
- **최근 수정일**: 2026-10-05 19:29
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
- `is_active`: 불리언 (진행 여부)
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
