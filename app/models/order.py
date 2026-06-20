from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from beanie import Document, Link, Indexed
from pydantic import Field


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentStatus(str, Enum):
    unpaid = "unpaid"
    paid = "paid"
    refunded = "refunded"


class OrderItem(Document):
    product_id: str
    slug: str
    name: str
    sku_label: str
    quantity: int
    unit_price: float

    class Settings:
        is_root = False


class ShippingAddress(Document):
    full_name: str
    phone: str
    line1: str
    line2: str = ""
    city: str
    state: str
    pincode: str
    country: str = "India"

    class Settings:
        is_root = False


class Order(Document):
    user_id: Optional[str] = None       # None = guest order
    guest_email: Optional[str] = None
    items: List[dict] = []              # List[OrderItem] serialised as dicts
    subtotal: float
    shipping_fee: float = 0.0
    total: float
    status: OrderStatus = OrderStatus.pending
    payment_status: PaymentStatus = PaymentStatus.unpaid
    shipping_address: dict = {}
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "orders"
