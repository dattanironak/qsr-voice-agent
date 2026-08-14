"""Import (upsert) a menu JSON file into Postgres.

Usage:
    python scripts/import_menu.py path/to/menu.json

Input shape: see 01-database-schema.md in qsr-agent-docs. Safe to re-run — categories, items,
groups, and options are upserted by their natural key (name scoped to parent), not inserted
blindly, so pushing an updated menu file updates existing rows in place.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    CustomizationGroup,
    CustomizationOption,
    MenuCategory,
    MenuItem,
)


def upsert_category(db: Session, data: dict, counts: dict) -> MenuCategory:
    stmt = (
        insert(MenuCategory)
        .values(name=data["name"], sort_order=data.get("sort_order", 0))
        .on_conflict_do_update(
            index_elements=["name"],
            set_={"sort_order": data.get("sort_order", 0)},
        )
        .returning(MenuCategory)
    )
    existing = db.execute(
        select(MenuCategory).where(MenuCategory.name == data["name"])
    ).scalar_one_or_none()
    counts["categories_created" if existing is None else "categories_updated"] += 1
    return db.execute(stmt).scalar_one()


def upsert_item(db: Session, category: MenuCategory, data: dict, counts: dict) -> MenuItem:
    existing = db.execute(
        select(MenuItem).where(
            MenuItem.category_id == category.id, MenuItem.name == data["name"]
        )
    ).scalar_one_or_none()
    counts["items_created" if existing is None else "items_updated"] += 1

    stmt = (
        insert(MenuItem)
        .values(
            category_id=category.id,
            name=data["name"],
            description=data.get("description"),
            price=data["price"],
            image_url=data.get("image_url"),
            sort_order=data.get("sort_order", 0),
            is_available=data.get("is_available", True),
        )
        .on_conflict_do_update(
            index_elements=["category_id", "name"],
            set_={
                "description": data.get("description"),
                "price": data["price"],
                "image_url": data.get("image_url"),
                "sort_order": data.get("sort_order", 0),
                "is_available": data.get("is_available", True),
            },
        )
        .returning(MenuItem)
    )
    return db.execute(stmt).scalar_one()


def upsert_group(db: Session, item: MenuItem, data: dict, counts: dict) -> CustomizationGroup:
    existing = db.execute(
        select(CustomizationGroup).where(
            CustomizationGroup.menu_item_id == item.id, CustomizationGroup.name == data["name"]
        )
    ).scalar_one_or_none()
    counts["groups_created" if existing is None else "groups_updated"] += 1

    stmt = (
        insert(CustomizationGroup)
        .values(
            menu_item_id=item.id,
            name=data["name"],
            is_required=data.get("is_required", False),
            max_choices=data.get("max_choices", 1),
            sort_order=data.get("sort_order", 0),
        )
        .on_conflict_do_update(
            index_elements=["menu_item_id", "name"],
            set_={
                "is_required": data.get("is_required", False),
                "max_choices": data.get("max_choices", 1),
                "sort_order": data.get("sort_order", 0),
            },
        )
        .returning(CustomizationGroup)
    )
    return db.execute(stmt).scalar_one()


def upsert_option(db: Session, group: CustomizationGroup, data: dict, counts: dict) -> None:
    existing = db.execute(
        select(CustomizationOption).where(
            CustomizationOption.group_id == group.id, CustomizationOption.name == data["name"]
        )
    ).scalar_one_or_none()
    counts["options_created" if existing is None else "options_updated"] += 1

    stmt = insert(CustomizationOption).values(
        group_id=group.id,
        name=data["name"],
        price_delta=data.get("price_delta", 0),
        sort_order=data.get("sort_order", 0),
        is_available=data.get("is_available", True),
    ).on_conflict_do_update(
        index_elements=["group_id", "name"],
        set_={
            "price_delta": data.get("price_delta", 0),
            "sort_order": data.get("sort_order", 0),
            "is_available": data.get("is_available", True),
        },
    )
    db.execute(stmt)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_menu.py path/to/menu.json")
        sys.exit(1)

    path = Path(sys.argv[1])
    payload = json.loads(path.read_text())

    counts = {
        "categories_created": 0,
        "categories_updated": 0,
        "items_created": 0,
        "items_updated": 0,
        "groups_created": 0,
        "groups_updated": 0,
        "options_created": 0,
        "options_updated": 0,
    }

    db = SessionLocal()
    try:
        for cat_idx, cat_data in enumerate(payload["categories"]):
            cat_data.setdefault("sort_order", cat_idx)
            category = upsert_category(db, cat_data, counts)

            for item_idx, item_data in enumerate(cat_data.get("items", [])):
                item_data.setdefault("sort_order", item_idx)
                item = upsert_item(db, category, item_data, counts)

                for group_idx, group_data in enumerate(item_data.get("customization_groups", [])):
                    group_data.setdefault("sort_order", group_idx)
                    group = upsert_group(db, item, group_data, counts)

                    for opt_idx, opt_data in enumerate(group_data.get("options", [])):
                        opt_data.setdefault("sort_order", opt_idx)
                        upsert_option(db, group, opt_data, counts)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Menu import complete:")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
