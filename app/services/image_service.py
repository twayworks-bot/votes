import io
import uuid
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps
from fastapi import UploadFile, HTTPException

from app.core.config import (
    UPLOAD_DIR,
    COVERS_DIR,
    ITEMS_DIR,
    MAX_IMAGE_WIDTH,
    IMAGE_QUALITY,
    ALLOWED_EXTENSIONS,
)


def validate_image_extension(filename: str) -> str:
    """이미지 확장자 유효성 검사 및 정규화"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식입니다. ({', '.join(sorted(ALLOWED_EXTENSIONS))} 허용)"
        )
    return ext


def process_and_save_image(
    file_bytes: bytes,
    target_dir: Path,
    max_width: int = MAX_IMAGE_WIDTH,
    quality: int = IMAGE_QUALITY
) -> Tuple[str, int, int]:
    """
    이미지 바이너리를 읽어 모바일 회전(EXIF) 보정 및 최대 폭(기본 1920px) 초과 시
    비율을 유지하며 리사이징 및 압축하여 저장합니다.

    Returns:
        (saved_filename, final_width, final_height)
    """
    try:
        image = Image.open(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"유효한 이미지 파일이 아닙니다: {str(e)}")

    # 1. EXIF 회전 메타데이터 자동 보정
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    orig_width, orig_height = image.size

    # 2. 가로 폭 1920px 초과 시 비율 유지 다운스케일링
    if orig_width > max_width:
        ratio = max_width / float(orig_width)
        new_height = max(1, int(orig_height * ratio))
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    else:
        new_height = orig_height

    final_width, final_height = image.size

    # 3. 투명도 처리 및 포맷 변환 (WebP 선호, 최적 압축)
    unique_name = f"{uuid.uuid4().hex}.webp"
    save_path = target_dir / unique_name

    # RGB 또는 RGBA 모드로 통일 (P, CMYK 등 변환)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
    else:
        image = image.convert("RGB")

    # 4. WebP 고효율 압축 저장
    image.save(save_path, format="WEBP", quality=quality, method=6)

    return unique_name, final_width, final_height


async def save_upload_image(upload_file: UploadFile, folder_type: str = "items") -> str:
    """
    FastAPI UploadFile을 받아 지정된 폴더('covers' 또는 'items')에 리사이즈 저장 후
    상대 파일 경로(예: 'items/xyz.webp')를 반환합니다.
    """
    if not upload_file or not upload_file.filename:
        raise HTTPException(status_code=400, detail="업로드할 파일이 제공되지 않았습니다.")

    validate_image_extension(upload_file.filename)

    content = await upload_file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

    target_dir = COVERS_DIR if folder_type == "covers" else ITEMS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    filename, _, _ = process_and_save_image(content, target_dir)
    return f"{folder_type}/{filename}"


def delete_stored_image(relative_path: Optional[str]) -> bool:
    """저장된 상대 경로의 이미지 파일을 물리적으로 삭제합니다."""
    if not relative_path:
        return False
    try:
        full_path = UPLOAD_DIR / relative_path
        if full_path.exists() and full_path.is_file():
            full_path.unlink()
            return True
    except Exception:
        pass
    return False
