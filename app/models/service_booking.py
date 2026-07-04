from typing import Optional
from datetime import datetime, timezone
from enum import Enum
from beanie import Document
from pydantic import Field


class BookingStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"


class BookingPaymentStatus(str, Enum):
    unpaid = "unpaid"
    paid = "paid"
    refunded = "refunded"


class ServiceBooking(Document):
    service_slug: str
    service_name: str
    amount: float                           # in INR
    customer_name: str
    customer_email: str
    customer_phone: str
    status: BookingStatus = BookingStatus.pending
    payment_status: BookingPaymentStatus = BookingPaymentStatus.unpaid
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_subscription_id: Optional[str] = None
    is_subscription: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "service_bookings"
