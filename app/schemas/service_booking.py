from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.service_booking import BookingStatus, BookingPaymentStatus, PaymentMethod


class ServiceBookingCreate(BaseModel):
    service_slug: str
    service_name: str
    amount: float
    customer_name: str
    customer_email: str
    customer_phone: str
    is_subscription: bool = False
    notes: str = ""


class ServiceBookingOut(BaseModel):
    id: str
    service_slug: str
    service_name: str
    amount: float
    customer_name: str
    customer_email: str
    customer_phone: str
    status: BookingStatus
    payment_status: BookingPaymentStatus
    payment_method: PaymentMethod
    razorpay_order_id: Optional[str]
    razorpay_subscription_id: Optional[str]
    is_subscription: bool
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingPaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class SubscriptionCreate(BaseModel):
    plan_id: str
    service_slug: str
    service_name: str
    amount: float
    customer_name: str
    customer_email: str
    customer_phone: str
    notes: str = ""


class SubscriptionPaymentVerify(BaseModel):
    razorpay_subscription_id: str
    razorpay_payment_id: str
    razorpay_signature: str
