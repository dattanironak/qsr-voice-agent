import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Order, OrderItem
from app.schemas import OrderCreate, OrderItemCustomizationIn, OrderItemOut, OrderOut, PaymentOut

router = APIRouter(prefix="/orders", tags=["orders"])

# Excludes visually ambiguous characters (0/O, 1/I) — this token gets read aloud and typed in at
# a physical pickup counter, not just displayed on screen.
_PICKUP_TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_pickup_token(db: Session) -> str:
    for _ in range(10):
        token = "".join(secrets.choice(_PICKUP_TOKEN_ALPHABET) for _ in range(5))
        exists = db.execute(select(Order.id).where(Order.pickup_token == token)).scalar_one_or_none()
        if exists is None:
            return token
    raise HTTPException(status_code=500, detail="Could not allocate a pickup token, try again")


def _to_order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        status=order.status,
        pickup_token=order.pickup_token,
        subtotal=order.subtotal,
        total=order.total,
        created_at=order.created_at,
        paid_at=order.paid_at,
        items=[
            OrderItemOut(
                id=item.id,
                menu_item_id=item.menu_item_id,
                name=item.menu_item_name_snapshot,
                quantity=item.qty,
                unit_price=item.unit_price,
                customizations=[OrderItemCustomizationIn(**c) for c in item.customizations_json],
                line_total=round(item.unit_price * item.qty, 2),
            )
            for item in order.items
        ],
        payments=[PaymentOut.model_validate(p) for p in order.payments],
    )


def _get_order_or_404(db: Session, order_id: uuid.UUID) -> Order:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .where(Order.id == order_id)
    )
    order = db.execute(stmt).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


@router.post("", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    order = Order(
        status="pending_payment",
        pickup_token=_generate_pickup_token(db),
        subtotal=body.subtotal,
        total=body.total,
        livekit_room_name=body.room_name,
    )
    db.add(order)
    db.flush()  # assign order.id before building child rows

    for item in body.items:
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=item.menu_item_id,
                menu_item_name_snapshot=item.name,
                qty=item.quantity,
                unit_price=item.unit_price,
                customizations_json=[c.model_dump() for c in item.customizations],
            )
        )

    db.commit()
    return _to_order_out(_get_order_or_404(db, order.id))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = _get_order_or_404(db, order_id)
    return _to_order_out(order)
