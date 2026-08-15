import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomizationOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price_delta: float
    is_available: bool
    sort_order: int


class CustomizationGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_required: bool
    max_choices: int
    sort_order: int
    options: list[CustomizationOptionOut]


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price: float
    is_available: bool
    image_url: str | None
    sort_order: int
    customization_groups: list[CustomizationGroupOut]


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    is_available: bool
    items: list[ItemOut]


class MenuResponse(BaseModel):
    categories: list[CategoryOut]


class SessionTokenRequest(BaseModel):
    customer_name: str | None = None


class SessionTokenResponse(BaseModel):
    livekit_url: str
    room_name: str
    token: str
    order_session_id: str


# ---- Admin: categories, items, customization groups/options ----


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    sort_order: int = 0
    is_available: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    sort_order: int | None = None
    is_available: bool | None = None


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    price: float = Field(ge=0)
    is_available: bool = True
    image_url: str | None = None
    sort_order: int = 0


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    is_available: bool | None = None
    image_url: str | None = None
    sort_order: int | None = None
    category_id: uuid.UUID | None = None


class CustomizationGroupCreate(BaseModel):
    name: str = Field(min_length=1)
    is_required: bool = False
    max_choices: int = Field(default=1, ge=1)
    sort_order: int = 0


class CustomizationGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    is_required: bool | None = None
    max_choices: int | None = Field(default=None, ge=1)
    sort_order: int | None = None


class CustomizationOptionCreate(BaseModel):
    name: str = Field(min_length=1)
    price_delta: float = 0
    is_available: bool = True
    sort_order: int = 0


class CustomizationOptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    price_delta: float | None = None
    is_available: bool | None = None
    sort_order: int | None = None


class UploadOut(BaseModel):
    url: str


# ---- Admin: auth ----


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AdminLoginOut(BaseModel):
    token: str
    expires_at: datetime
    username: str
    role: str


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: str


# ---- Conversation recording ----


class ConversationSessionCreate(BaseModel):
    room_name: str = Field(min_length=1)


class ConversationTurnCreate(BaseModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ConversationTurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ConversationSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_name: str
    started_at: datetime
    ended_at: datetime | None
    turns: list[ConversationTurnOut]


# ---- Orders / checkout ----


class OrderItemCustomizationIn(BaseModel):
    group_name: str
    option_name: str
    price_delta: float = 0


class OrderItemIn(BaseModel):
    menu_item_id: uuid.UUID
    name: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    customizations: list[OrderItemCustomizationIn] = Field(default_factory=list)


class OrderCreate(BaseModel):
    room_name: str = Field(min_length=1)
    items: list[OrderItemIn] = Field(min_length=1)
    subtotal: float = Field(ge=0)
    total: float = Field(ge=0)


class OrderItemOut(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    unit_price: float
    customizations: list[OrderItemCustomizationIn]
    line_total: float


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    provider_ref: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class OrderOut(BaseModel):
    id: uuid.UUID
    status: str
    pickup_token: str
    subtotal: float
    total: float
    created_at: datetime
    paid_at: datetime | None
    items: list[OrderItemOut]
    payments: list[PaymentOut]


class PayuCheckoutOut(BaseModel):
    action_url: str
    fields: dict[str, str]
