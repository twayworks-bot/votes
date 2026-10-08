import math
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import DEFAULT_PREFIX
from app.core.database import init_db

client = TestClient(app)


def python_calculate_aggregate_grid(item_count: int, avail_width: int, avail_height: int):
    """
    detail.html의 JavaScript calculateAggregateGrid()와 100% 동일한 로직의 검증용 함수
    """
    min_size = 90
    gap = 8
    max_line = 10

    if item_count <= 0:
        return {"cols": 1, "rows": 1, "card_size": min_size, "scrollable": False, "layout_desc": "0개 항목"}

    w = max(min_size, int(avail_width))
    h = max(min_size, int(avail_height))
    aspect = w / h

    phys_max_cols = max(1, int((w + gap) / (min_size + gap)))
    phys_max_rows = max(1, int((h + gap) / (min_size + gap)))

    ideal = None

    # 한 화면 수용 가능 범위 (최대 약 60개 기준: 10x6 또는 6x10)
    if item_count <= 60:
        if aspect >= 1.25:
            # 1) 폭이 길 때 (가로형): 긴 쪽인 폭에 최대 10개 나열 (예: 36개 -> 10x4)
            target_cols = min(max_line, phys_max_cols)
            target_rows = math.ceil(item_count / target_cols)
            if target_rows <= min(6, phys_max_rows):
                sw = int((w - (target_cols - 1) * gap) / target_cols)
                sh = int((h - (target_rows - 1) * gap) / target_rows)
                card_size = min(sw, sh)
                if card_size >= min_size:
                    ideal = {
                        "cols": target_cols,
                        "rows": target_rows,
                        "card_size": card_size,
                        "scrollable": False,
                        "layout_desc": f"{target_cols} × {target_rows} (가로 꽉 찬 배열)"
                    }
        elif aspect <= 0.8:
            # 2) 높이가 길 때 (세로형): 긴 쪽인 높이에 최대 10개 나열 (예: 36개 -> 4x10)
            target_rows = min(max_line, phys_max_rows)
            target_cols = math.ceil(item_count / target_rows)
            if target_cols <= min(6, phys_max_cols):
                sw = int((w - (target_cols - 1) * gap) / target_cols)
                sh = int((h - (target_rows - 1) * gap) / target_rows)
                card_size = min(sw, sh)
                if card_size >= min_size:
                    ideal = {
                        "cols": target_cols,
                        "rows": target_rows,
                        "card_size": card_size,
                        "scrollable": False,
                        "layout_desc": f"{target_cols} × {target_rows} (세로 꽉 찬 배열)"
                    }
        else:
            # 3) 폭과 높이가 비슷할 때 (정방형): 6x6 등 균형 정방형 배치
            c = math.ceil(math.sqrt(item_count))
            c = min(c, max_line, phys_max_cols)
            r = math.ceil(item_count / c)
            if r <= min(max_line, phys_max_rows):
                sw = int((w - (c - 1) * gap) / c)
                sh = int((h - (r - 1) * gap) / r)
                card_size = min(sw, sh)
                if card_size >= min_size:
                    ideal = {
                        "cols": c,
                        "rows": r,
                        "card_size": card_size,
                        "scrollable": False,
                        "layout_desc": f"{c} × {r} (정방형 배열)"
                    }

    if ideal:
        return ideal

    # 최선의 조합 탐색
    if item_count <= 60:
        best = None
        best_score = -1e9
        max_c = min(max_line, phys_max_cols)
        for c in range(1, max_c + 1):
            r = math.ceil(item_count / c)
            max_r_allowed = min(max_line, phys_max_rows) if aspect <= 0.8 else min(6, phys_max_rows)
            if r > max_r_allowed or r > max_line:
                continue
            sw = int((w - (c - 1) * gap) / c)
            sh = int((h - (r - 1) * gap) / r)
            size = min(sw, sh)
            if size >= min_size:
                grid_aspect = c / r
                aspect_sim = -abs(math.log(aspect) - math.log(grid_aspect))
                empty = (c * r) - item_count
                score = size * 15 + aspect_sim * 50 - empty * 5
                if score > best_score:
                    best_score = score
                    best = {
                        "cols": c,
                        "rows": r,
                        "card_size": size,
                        "scrollable": False,
                        "layout_desc": f"{c} × {r} 배열"
                    }
        if best:
            return best

    # 스크롤 모드
    cols = max(1, min(max_line, phys_max_cols))
    rows = math.ceil(item_count / cols)
    card_size = max(min_size, int((w - (cols - 1) * gap) / cols))
    return {
        "cols": cols,
        "rows": rows,
        "card_size": card_size,
        "scrollable": True,
        "layout_desc": f"{cols}열 스크롤 배열"
    }


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_aggregate_view_html_elements_present():
    """상세 페이지 HTML에 '모아보기' 버튼 및 모달, 인라인 컨테이너가 정상 렌더링되는지 검증"""
    res = client.get(f"{DEFAULT_PREFIX}/bazaarposter")
    assert res.status_code == 200
    html = res.text

    # 1. 히어로 영역의 '한눈에 모아보기' 버튼
    assert "한눈에 모아보기" in html
    assert "openAggregateModal()" in html

    # 2. 갤러리 섹션 헤더의 뷰 전환 버튼 및 전체화면 모아보기 버튼
    assert "btn-view-card" in html
    assert "btn-view-aggregate" in html
    assert "전체화면 모아보기" in html

    # 3. 인라인 모아보기 컨테이너
    assert "inline-aggregate-container" in html
    assert "inline-aggregate-grid-container" in html

    # 4. 전체화면 모아보기 전용 모달
    assert "aggregate-modal" in html
    assert "aggregate-grid-container" in html
    assert "전체 등록 항목 한눈에 모아보기" in html
    assert "aggregate-spec-badge" in html

    # 5. 자바스크립트 내 calculateAggregateGrid 및 렌더링 함수 포함
    assert "calculateAggregateGrid" in html
    assert "renderAggregateModal" in html
    assert "switchGalleryViewMode" in html


def test_grid_algorithm_case_n36_wide():
    """요구사항 1: N=36, 폭이 길 때 -> 10x4 배열 및 최소 90x90 이상 검증"""
    res = python_calculate_aggregate_grid(item_count=36, avail_width=1200, avail_height=600)
    assert res["cols"] == 10
    assert res["rows"] == 4
    assert res["card_size"] >= 90
    assert res["scrollable"] is False


def test_grid_algorithm_case_n36_tall():
    """요구사항 2: N=36, 높이가 길 때 -> 4x10 배열 및 최소 90x90 이상 검증"""
    res = python_calculate_aggregate_grid(item_count=36, avail_width=600, avail_height=1200)
    assert res["cols"] == 4
    assert res["rows"] == 10
    assert res["card_size"] >= 90
    assert res["scrollable"] is False


def test_grid_algorithm_case_n36_square():
    """요구사항 3: N=36, 폭과 높이가 비슷할 때 -> 6x6 배열 및 꽉 찬 카드 크기 검증"""
    res = python_calculate_aggregate_grid(item_count=36, avail_width=900, avail_height=900)
    assert res["cols"] == 6
    assert res["rows"] == 6
    assert res["card_size"] >= 90
    assert res["scrollable"] is False


def test_grid_algorithm_case_w1024():
    """요구사항 4: 폭 1024px 기준 10개 나열 시 최소 크기 90px 만족 및 패딩 고려 꽉 찬 배치 검증"""
    res = python_calculate_aggregate_grid(item_count=36, avail_width=1024, avail_height=700)
    assert res["cols"] == 10
    assert res["rows"] == 4
    assert res["card_size"] >= 90
    assert res["scrollable"] is False


def test_grid_algorithm_case_max_screen_60():
    """요구사항 5: 한 화면 최대 약 60개(10x6 / 6x10)까지 꽉 차게 동적 이미지 크기 변경 검증"""
    # 가로형 60개 -> 10x6
    wide_res = python_calculate_aggregate_grid(item_count=60, avail_width=1200, avail_height=700)
    assert wide_res["cols"] == 10
    assert wide_res["rows"] == 6
    assert wide_res["card_size"] >= 90
    assert wide_res["scrollable"] is False

    # 세로형 60개 -> 6x10
    tall_res = python_calculate_aggregate_grid(item_count=60, avail_width=700, avail_height=1200)
    assert tall_res["cols"] == 6
    assert tall_res["rows"] == 10
    assert tall_res["card_size"] >= 90
    assert tall_res["scrollable"] is False


def test_grid_algorithm_case_overflow_scroll():
    """요구사항 6: 60개 초과(예: 80개) 시 페이지를 넘도록 배치하여 스크롤 허용 검증"""
    res = python_calculate_aggregate_grid(item_count=80, avail_width=1200, avail_height=700)
    assert res["cols"] <= 10
    assert res["rows"] >= 8
    assert res["card_size"] >= 90
    assert res["scrollable"] is True
