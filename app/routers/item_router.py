from typing import Optional
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.item_schema import ItemResponse, ItemVerifyPin
from app.services import item_service, image_service

router = APIRouter(prefix="/api/items", tags=["items"])


@router.post("", response_model=ItemResponse)
async def create_item_endpoint(
    event_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    pin: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """참여 항목 등록 (이미지 1920px 리사이즈 및 핀번호 암호화 저장)"""
    if not image or not image.filename:
        raise HTTPException(status_code=400, detail="작품 이미지 파일은 필수입니다.")

    image_path = await image_service.save_upload_image(image, folder_type="items")

    item = item_service.create_item(
        db=db,
        event_id=event_id,
        title=title,
        description=description,
        image_path=image_path,
        pin=pin
    )
    return item


@router.get("/{item_id}", response_model=ItemResponse)
def get_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    """항목 상세 정보 조회 (모달용)"""
    item = item_service.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    return item


@router.post("/{item_id}/update", response_model=ItemResponse)
async def update_item_endpoint(
    item_id: int,
    pin: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """항목 수정 (핀번호 인증 필수)"""
    new_image_path = None
    if image and image.filename:
        new_image_path = await image_service.save_upload_image(image, folder_type="items")

    updated_item = item_service.update_item(
        db=db,
        item_id=item_id,
        pin=pin,
        title=title,
        description=description,
        new_image_path=new_image_path
    )
    return updated_item


@router.post("/{item_id}/delete")
def delete_item_endpoint(
    item_id: int,
    body: ItemVerifyPin,
    db: Session = Depends(get_db)
):
    """항목 삭제 (핀번호 인증 필수)"""
    success = item_service.delete_item(db=db, item_id=item_id, pin=body.pin)
    return {"success": success, "message": "성공적으로 삭제되었습니다."}
