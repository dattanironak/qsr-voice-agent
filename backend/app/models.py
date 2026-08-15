import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class MenuCategory(Base):
    __tablename__ = "menu_categories"
    __table_args__ = (UniqueConstraint("name", name="uq_menu_categories_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="MenuItem.sort_order"
    )


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_menu_items_category_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_categories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    customization_groups: Mapped[list["CustomizationGroup"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="CustomizationGroup.sort_order",
    )


class CustomizationGroup(Base):
    __tablename__ = "customization_groups"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "name", name="uq_customization_groups_item_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_choices: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="customization_groups")
    options: Mapped[list["CustomizationOption"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="CustomizationOption.sort_order",
    )


class CustomizationOption(Base):
    __tablename__ = "customization_options"
    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_customization_options_group_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customization_groups.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_delta: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    group: Mapped["CustomizationGroup"] = relationship(back_populates="options")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending_payment")
    pickup_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    livekit_room_name: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False
    )
    menu_item_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    customizations_json: Mapped[list] = mapped_column(JSONB, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="payu")
    provider_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="initiated")
    raw_webhook_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="payments")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="owner")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    room_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    turns: Mapped[list["ConversationTurn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ConversationTurn.created_at"
    )


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    session: Mapped["ConversationSession"] = relationship(back_populates="turns")
