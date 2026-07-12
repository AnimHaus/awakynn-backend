from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.order import OrderStatus, PaymentStatus


class OrderItemIn(BaseModel):
    product_id: str
    slug: str
    name: str
    sku_label: str
    quantity: int
    unit_price: float


class ShippingAddressIn(BaseModel):
    full_name: str
    phone: str
    line1: str
    line2: str = ""
    city: str
    state: str
    pincode: str
    country: str = "India"


class OrderCreate(BaseModel):
    items: List[OrderItemIn]
    shipping_address: ShippingAddressIn
    guest_email: Optional[str] = None
    notes: str = ""


class OrderOut(BaseModel):
    id: str
    user_id: Optional[str]
    guest_email: Optional[str]
    items: List[dict]
    subtotal: float
    shipping_fee: float
    total: float
    status: OrderStatus
    payment_status: PaymentStatus
    shipping_address: dict
    razorpay_order_id: Optional[str]
    razorpay_invoice_id: Optional[str] = None
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# Public-safe tracking response — never exposes full email or payment IDs
class OrderTrackOut(BaseModel):
    id: str
    razorpay_order_id: Optional[str] = None
    items: List[dict]
    subtotal: float
    shipping_fee: float
    total: float
    status: OrderStatus
    payment_status: PaymentStatus
    shipping_address: dict
    notes: str
    created_at: datetime
    updated_at: datetime
    # Partially masked email so user can confirm it's theirs
    masked_email: Optional[str] = None

    model_config = {"from_attributes": True}


class TrackByEmailRequest(BaseModel):
    email: str
