from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_role
from app.database import get_db
from app.models import AdminUser, Order
from app.routers.orders import _to_order_out
from app.schemas import OrderOut

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


@router.get("", response_model=list[OrderOut])
def list_orders(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role("owner", "treasurer")),
):
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .order_by(Order.created_at.desc())
    )
    if admin.role == "treasurer":
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = stmt.where(Order.created_at >= today_start)

    orders = db.execute(stmt).scalars().all()
    return [_to_order_out(order) for order in orders]
