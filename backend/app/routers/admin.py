import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import CustomizationGroup, CustomizationOption, MenuCategory, MenuItem
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    CustomizationGroupCreate,
    CustomizationGroupOut,
    CustomizationGroupUpdate,
    CustomizationOptionCreate,
    CustomizationOptionOut,
    CustomizationOptionUpdate,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    UploadOut,
)
from app.storage import UPLOAD_DIR

router = APIRouter(prefix="/admin", tags=["admin"])

IMAGE_EXTENSION_BY_CONTENT_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _category_tree_query():
    return select(MenuCategory).options(
        selectinload(MenuCategory.items)
        .selectinload(MenuItem.customization_groups)
        .selectinload(CustomizationGroup.options)
    )


def _apply(obj, data: dict) -> None:
    for field, value in data.items():
        setattr(obj, field, value)


# ---- categories ----


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    stmt = _category_tree_query().order_by(MenuCategory.sort_order)
    return db.execute(stmt).unique().scalars().all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    category = MenuCategory(name=body.name, sort_order=body.sort_order)
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"A category named '{body.name}' already exists")
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: uuid.UUID, body: CategoryUpdate, db: Session = Depends(get_db)):
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    _apply(category, body.model_dump(exclude_unset=True))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A category with that name already exists")
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    db.delete(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Cannot delete this category: one of its items is referenced by past orders. "
            "Mark the items unavailable instead.",
        )


# ---- items ----


@router.post("/categories/{category_id}/items", response_model=ItemOut, status_code=201)
def create_item(category_id: uuid.UUID, body: ItemCreate, db: Session = Depends(get_db)):
    if db.get(MenuCategory, category_id) is None:
        raise HTTPException(404, "Category not found")
    item = MenuItem(category_id=category_id, **body.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"An item named '{body.name}' already exists in this category")
    db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: uuid.UUID, body: ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("category_id") is not None and db.get(MenuCategory, data["category_id"]) is None:
        raise HTTPException(404, "Target category not found")
    _apply(item, data)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An item with that name already exists in this category")
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Cannot delete this item: it is referenced by past orders. Mark it unavailable instead.",
        )


# ---- customization groups ----


@router.post("/items/{item_id}/groups", response_model=CustomizationGroupOut, status_code=201)
def create_group(item_id: uuid.UUID, body: CustomizationGroupCreate, db: Session = Depends(get_db)):
    if db.get(MenuItem, item_id) is None:
        raise HTTPException(404, "Item not found")
    group = CustomizationGroup(menu_item_id=item_id, **body.model_dump())
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"A group named '{body.name}' already exists for this item")
    db.refresh(group)
    return group


@router.patch("/groups/{group_id}", response_model=CustomizationGroupOut)
def update_group(group_id: uuid.UUID, body: CustomizationGroupUpdate, db: Session = Depends(get_db)):
    group = db.get(CustomizationGroup, group_id)
    if group is None:
        raise HTTPException(404, "Group not found")
    _apply(group, body.model_dump(exclude_unset=True))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A group with that name already exists for this item")
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    group = db.get(CustomizationGroup, group_id)
    if group is None:
        raise HTTPException(404, "Group not found")
    db.delete(group)
    db.commit()


# ---- customization options ----


@router.post("/groups/{group_id}/options", response_model=CustomizationOptionOut, status_code=201)
def create_option(group_id: uuid.UUID, body: CustomizationOptionCreate, db: Session = Depends(get_db)):
    if db.get(CustomizationGroup, group_id) is None:
        raise HTTPException(404, "Group not found")
    option = CustomizationOption(group_id=group_id, **body.model_dump())
    db.add(option)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"An option named '{body.name}' already exists in this group")
    db.refresh(option)
    return option


@router.patch("/options/{option_id}", response_model=CustomizationOptionOut)
def update_option(option_id: uuid.UUID, body: CustomizationOptionUpdate, db: Session = Depends(get_db)):
    option = db.get(CustomizationOption, option_id)
    if option is None:
        raise HTTPException(404, "Option not found")
    _apply(option, body.model_dump(exclude_unset=True))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An option with that name already exists in this group")
    db.refresh(option)
    return option


@router.delete("/options/{option_id}", status_code=204)
def delete_option(option_id: uuid.UUID, db: Session = Depends(get_db)):
    option = db.get(CustomizationOption, option_id)
    if option is None:
        raise HTTPException(404, "Option not found")
    db.delete(option)
    db.commit()


# ---- image uploads ----


@router.post("/uploads", response_model=UploadOut, status_code=201)
def upload_image(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    extension = IMAGE_EXTENSION_BY_CONTENT_TYPE.get(file.content_type or "")
    if extension is None:
        raise HTTPException(415, "Unsupported image type. Use PNG, JPEG, WEBP, or GIF.")

    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image too large (max 5MB)")

    filename = f"{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / filename).write_bytes(contents)

    url = f"{settings.backend_public_base_url.rstrip('/')}/uploads/{filename}"
    return UploadOut(url=url)
