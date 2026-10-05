import io
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Windows 콘솔 UTF-8 출력 지원
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DEFAULT_PREFIX, UPLOAD_DIR
from app.core.database import SessionLocal, init_db
from app.models.event import Event
from app.models.item import EventItem
from app.services import event_service, item_service, vote_service, image_service



def create_sample_poster_image(width: int, height: int, title_text: str, bg_color: tuple) -> bytes:
    """
    테스트용 바자회 홍보 포스터 이미지를 지정된 해상도(width x height)로 동적 생성합니다.
    """
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 장식 프레임
    border_margin = int(width * 0.03)
    draw.rectangle(
        [(border_margin, border_margin), (width - border_margin, height - border_margin)],
        outline=(255, 255, 255),
        width=int(width * 0.01)
    )

    # 중앙 원형 배너
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 3
    draw.ellipse(
        [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
        fill=(255, 255, 255, 60),
        outline=(255, 255, 255),
        width=int(width * 0.005)
    )

    # 안내 텍스트 영역 (시스템 기본 폰트 사용)
    # Pillow의 기본 텍스트 렌더링
    draw.text((border_margin + 50, border_margin + 50), f"[BAAZAR POSTER 2026] {title_text}", fill=(255, 255, 255))
    draw.text((border_margin + 50, border_margin + 120), f"Original Resolution: {width}x{height}", fill=(255, 255, 200))
    draw.text((center_x - 150, center_y), title_text, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def run_seed_and_test():
    print("=" * 60)
    print(" [*] VoteEvent 첫 이벤트('baazarposter') 시드 등록 및 기능 검증")
    print("=" * 60)

    # 1. DB 초기화
    init_db()
    db = SessionLocal()

    try:
        # 2. 첫 이벤트 'baazarposter' 등록 여부 확인 및 생성
        event_slug = "baazarposter"
        event_title = "바자회 홍보 포스터 자랑대회"
        event_desc = (
            "2026 우리 동네 나눔 바자회에 사용할 홍보 포스터를 뽑는 자랑대회입니다!\n"
            "여러분이 직접 제작한 멋진 포스터를 자유롭게 등록하고,\n"
            "가장 마음에 드는 포스터에 '좋아요' 투표를 해주세요!"
        )

        existing_event = event_service.get_event_by_slug(db, event_slug)
        if existing_event:
            print(f"[*] 기존 이벤트 '{event_slug}'가 이미 존재하여 삭제 후 새로 갱신합니다.")
            event_service.delete_event(db, existing_event.id)

        # 이벤트 대표 커버 이미지 생성 (2400x1200 - 1920px 초과 대형 이미지)
        print("\n[Step 1] 1920px 초과 대형 대표 커버 이미지 생성 중 (2400 x 1200)...")
        cover_raw = create_sample_poster_image(2400, 1200, "Baazar Event Official Cover", (225, 29, 72))
        cover_filename, c_w, c_h = image_service.process_and_save_image(cover_raw, image_service.COVERS_DIR)
        print(f" -> 원본 2400px -> 최적화 변환 결과: {c_w}x{c_h} (저장 파일: covers/{cover_filename})")
        assert c_w == 1920, f"커버 이미지 가로 폭이 1920px로 리사이즈되어야 합니다! (실제: {c_w})"

        event = event_service.create_event(
            db=db,
            slug=event_slug,
            title=event_title,
            description=event_desc,
            cover_image=f"covers/{cover_filename}"
        )
        print(f"[OK] 첫 이벤트 생성 완료! (ID: {event.id}, Slug: {event.slug}, Title: {event.title})")

        # 3. 참여자 항목 등록 테스트
        # 참여자 1: 2560x1440 대형 이미지 업로드 (1920px 다운스케일링 대상)
        print("\n[Step 2] 참여자 1: 바자회홍보포스터 대형 이미지 생성 (2560 x 1440)...")
        poster1_raw = create_sample_poster_image(2560, 1440, "행복 가득 나눔 바자회 포스터", (37, 99, 235))
        p1_filename, p1_w, p1_h = image_service.process_and_save_image(poster1_raw, image_service.ITEMS_DIR)
        print(f" -> 원본 2560px -> 최적화 변환 결과: {p1_w}x{p1_h} (저장 파일: items/{p1_filename})")
        assert p1_w == 1920, f"참여 항목 1의 가로 폭이 1920px로 리사이즈되어야 합니다! (실제: {p1_w})"

        item1 = item_service.create_item(
            db=db,
            event_id=event.id,
            title="행복 가득 나눔 바자회 포스터 (작성자: 김나눔)",
            description="이웃과 함께하는 따뜻한 봄날의 행복 바자회 공식 포스터 출품작입니다. 많은 투표 부탁드립니다!",
            image_path=f"items/{p1_filename}",
            pin="1234"
        )
        print(f"[OK] 참여자 1 항목 등록 성공! (ID: {item1.id}, Title: {item1.title})")

        # 참여자 2: 1600x1200 이미지 업로드 (1920px 이하이므로 원본 폭 유지)
        print("\n[Step 3] 참여자 2: 바자회홍보포스터 이미지 생성 (1600 x 1200)...")
        poster2_raw = create_sample_poster_image(1600, 1200, "다함께 즐기는 플리마켓 & 바자회", (16, 185, 129))
        p2_filename, p2_w, p2_h = image_service.process_and_save_image(poster2_raw, image_service.ITEMS_DIR)
        print(f" -> 원본 1600px -> 변환 결과: {p2_w}x{p2_h} (저장 파일: items/{p2_filename})")
        assert p2_w == 1600, f"1920px 이하 이미지는 원본 폭이 유지되어야 합니다! (실제: {p2_w})"

        item2 = item_service.create_item(
            db=db,
            event_id=event.id,
            title="다함께 즐기는 플리마켓 & 바자회 포스터 (작성자: 이기쁨)",
            description="다양한 중고 물품과 맛있는 먹거리 장터가 함께 열립니다. 꼭 놀러오세요~",
            image_path=f"items/{p2_filename}",
            pin="5678"
        )
        print(f"[OK] 참여자 2 항목 등록 성공! (ID: {item2.id}, Title: {item2.title})")

        # 4. 투표 기능 테스트
        print("\n[Step 4] 좋아요(투표) 기능 검증...")
        v1 = vote_service.register_vote(db, item1.id, "voter_user_A")
        print(f" -> 유저 A 투표 결과: success={v1['success']}, vote_count={v1['vote_count']}")
        assert v1["success"] is True and v1["vote_count"] == 1

        # 유저 A의 중복 투표 시도
        v1_dup = vote_service.register_vote(db, item1.id, "voter_user_A")
        print(f" -> 유저 A 중복 투표 방어 확인: already_voted={v1_dup['already_voted']}, message='{v1_dup['message']}'")
        assert v1_dup["already_voted"] is True and v1_dup["vote_count"] == 1

        # 유저 B의 투표
        v2 = vote_service.register_vote(db, item1.id, "voter_user_B")
        print(f" -> 유저 B 투표 결과: vote_count={v2['vote_count']}")
        assert v2["vote_count"] == 2

        # 5. 핀번호 검증 수정 및 삭제 테스트
        print("\n[Step 5] 핀번호(PIN) 인증 기반 수정 검증...")
        # 오입력 테스트
        try:
            item_service.update_item(db, item1.id, pin="9999", title="제목 변경 시도")
            print(" [X] 오류: 잘못된 핀번호인데 수정이 허용되었습니다!")
            assert False
        except Exception as e:
            print(f" [OK] 잘못된 핀번호 거부 성공: {getattr(e, 'detail', str(e))}")

        # 정상 핀번호 수정
        updated = item_service.update_item(db, item1.id, pin="1234", title="[수정됨] 행복 가득 나눔 바자회 포스터")
        print(f" [OK] 올바른 핀번호로 수정 완료: {updated.title}")
        assert "[수정됨]" in updated.title

        print("\n" + "=" * 60)
        print(" [SUCCESS] 모든 시드 등록 및 핵심 기능 검증이 성공적으로 완료되었습니다!")
        print(f" - 접속 URL: http://localhost:5000{DEFAULT_PREFIX}/{event_slug}")
        print(f" - 관리자 URL: http://localhost:5000{DEFAULT_PREFIX}")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    run_seed_and_test()
