from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CustomizationGroup, MenuCategory, MenuItem
from app.schemas import (
    CategoryOut,
    CustomizationGroupOut,
    CustomizationOptionOut,
    ItemOut,
    MenuResponse,
)

router = APIRouter()


@router.get("/menu", response_model=MenuResponse)
def get_menu(db: Session = Depends(get_db)) -> MenuResponse:
    stmt = (
        select(MenuCategory)
        .options(
            selectinload(MenuCategory.items)
            .selectinload(MenuItem.customization_groups)
            .selectinload(CustomizationGroup.options)
        )
        .order_by(MenuCategory.sort_order)
    )
    categories = db.execute(stmt).unique().scalars().all()

    out: list[CategoryOut] = []
    for category in categories:
        if not category.is_available:
            continue
        items_out: list[ItemOut] = []
        for item in sorted(category.items, key=lambda i: i.sort_order):
            if not item.is_available:
                continue
            groups_out: list[CustomizationGroupOut] = []
            for group in sorted(item.customization_groups, key=lambda g: g.sort_order):
                options_out = [
                    CustomizationOptionOut.model_validate(o)
                    for o in sorted(group.options, key=lambda o: o.sort_order)
                    if o.is_available
                ]
                groups_out.append(
                    CustomizationGroupOut(
                        id=group.id,
                        name=group.name,
                        is_required=group.is_required,
                        max_choices=group.max_choices,
                        sort_order=group.sort_order,
                        options=options_out,
                    )
                )
            items_out.append(
                ItemOut(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    price=item.price,
                    is_available=item.is_available,
                    image_url=item.image_url,
                    sort_order=item.sort_order,
                    customization_groups=groups_out,
                )
            )
        out.append(
            CategoryOut(
                id=category.id,
                name=category.name,
                sort_order=category.sort_order,
                is_available=category.is_available,
                items=items_out,
            )
        )

    return MenuResponse(categories=out)
