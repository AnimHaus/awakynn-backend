import hashlib
import hmac
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.core.deps import require_admin
from app.models.service_booking import BookingPaymentStatus, BookingStatus, PaymentMethod, ServiceBooking
from app.models.user import User
from app.schemas.service_booking import (
    BookingPaymentVerify,
    ServiceBookingCreate,
    ServiceBookingOut,
    SubscriptionCreate,
    SubscriptionPaymentVerify,
)

router = APIRouter(prefix="/services", tags=["services"])


def _serialize(b: ServiceBooking) -> dict:
    return {
        "id": str(b.id),
        "service_slug": b.service_slug,
        "service_name": b.service_name,
        "amount": b.amount,
        "customer_name": b.customer_name,
        "customer_email": b.customer_email,
        "customer_phone": b.customer_phone,
        "status": b.status,
        "payment_status": b.payment_status,
        "payment_method": b.payment_method,
        "razorpay_order_id": b.razorpay_order_id,
        "razorpay_subscription_id": b.razorpay_subscription_id,
        "is_subscription": b.is_subscription,
        "notes": b.notes,
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


# ── One-time booking ─────────────────────────────────────────────────────────

@router.post("/bookings/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_booking(body: ServiceBookingCreate):
    """Create a service booking and return a Razorpay order to pay."""
    import razorpay

    booking = ServiceBooking(
        service_slug=body.service_slug,
        service_name=body.service_name,
        amount=body.amount,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        notes=body.notes,
    )
    await booking.insert()

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    rz_order = client.order.create({
        "amount": int(body.amount * 100),
        "currency": "INR",
        "receipt": str(booking.id),
        "payment_capture": 1,
        "notes": {
            "service": body.service_slug,
            "customer_email": body.customer_email,
        },
    })

    await booking.set({"razorpay_order_id": rz_order["id"]})

    return {
        "booking_id": str(booking.id),
        "razorpay_order_id": rz_order["id"],
        "amount": rz_order["amount"],
        "currency": rz_order["currency"],
        "key_id": settings.RAZORPAY_KEY_ID,
    }


@router.post("/bookings/{booking_id}/verify-payment", response_model=ServiceBookingOut)
async def verify_booking_payment(booking_id: str, body: BookingPaymentVerify):
    booking = await ServiceBooking.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    msg = f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")

    await booking.set({
        "payment_status": BookingPaymentStatus.paid,
        "status": BookingStatus.confirmed,
        "razorpay_payment_id": body.razorpay_payment_id,
    })
    return _serialize(booking)


# ── Subscription booking ─────────────────────────────────────────────────────

@router.post("/subscriptions/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_subscription(body: SubscriptionCreate):
    """Create a Razorpay subscription from an existing plan and return subscription_id."""
    import razorpay

    booking = ServiceBooking(
        service_slug=body.service_slug,
        service_name=body.service_name,
        amount=body.amount,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        is_subscription=True,
        notes=body.notes,
    )
    await booking.insert()

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    rz_sub = client.subscription.create({
        "plan_id": body.plan_id,
        "total_count": 12,          # 12 monthly charges
        "quantity": 1,
        "customer_notify": 1,
        "notes": {
            "service": body.service_slug,
            "customer_email": body.customer_email,
            "booking_id": str(booking.id),
        },
    })

    await booking.set({"razorpay_subscription_id": rz_sub["id"]})

    return {
        "booking_id": str(booking.id),
        "subscription_id": rz_sub["id"],
        "key_id": settings.RAZORPAY_KEY_ID,
    }


@router.post("/subscriptions/{booking_id}/verify-payment", response_model=ServiceBookingOut)
async def verify_subscription_payment(booking_id: str, body: SubscriptionPaymentVerify):
    booking = await ServiceBooking.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Razorpay subscription signature: payment_id|subscription_id
    msg = f"{body.razorpay_payment_id}|{body.razorpay_subscription_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")

    await booking.set({
        "payment_status": BookingPaymentStatus.paid,
        "status": BookingStatus.confirmed,
        "razorpay_payment_id": body.razorpay_payment_id,
        "razorpay_subscription_id": body.razorpay_subscription_id,
    })
    return _serialize(booking)


# ── Cash payment (public) ────────────────────────────────────────────────────

@router.post("/bookings/cash", response_model=ServiceBookingOut, status_code=status.HTTP_201_CREATED)
async def create_cash_booking(body: ServiceBookingCreate):
    """Public endpoint: customer opts to pay by cash. Booking is confirmed but unpaid pending admin collection."""
    from datetime import datetime, timezone
    booking = ServiceBooking(
        service_slug=body.service_slug,
        service_name=body.service_name,
        amount=body.amount,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        is_subscription=body.is_subscription,
        payment_method=PaymentMethod.cash,
        payment_status=BookingPaymentStatus.unpaid,
        status=BookingStatus.confirmed,
        notes=body.notes,
    )
    await booking.insert()
    return _serialize(booking)


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/bookings/", response_model=List[ServiceBookingOut])
async def list_bookings(
    _: Annotated[User, Depends(require_admin)],
    status_filter: Optional[BookingStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = ServiceBooking.find(ServiceBooking.status == status_filter) if status_filter else ServiceBooking.find()
    bookings = await query.sort(-ServiceBooking.created_at).skip(skip).limit(limit).to_list()
    return [_serialize(b) for b in bookings]


@router.patch("/bookings/{booking_id}/status", response_model=ServiceBookingOut)
async def update_booking_status(
    booking_id: str,
    body: dict,
    _: Annotated[User, Depends(require_admin)],
):
    booking = await ServiceBooking.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    await booking.set({"status": body.get("status")})
    return _serialize(booking)


@router.patch("/bookings/{booking_id}/payment", response_model=ServiceBookingOut)
async def update_booking_payment(
    booking_id: str,
    body: dict,
    _: Annotated[User, Depends(require_admin)],
):
    """Admin endpoint to manually set payment status and method (e.g. cash)."""
    booking = await ServiceBooking.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    update: dict = {}
    if "payment_status" in body:
        update["payment_status"] = body["payment_status"]
    if "payment_method" in body:
        update["payment_method"] = body["payment_method"]
    if update:
        from datetime import datetime, timezone
        update["updated_at"] = datetime.now(timezone.utc)
        await booking.set(update)
    return _serialize(booking)


@router.post("/bookings/manual", response_model=ServiceBookingOut, status_code=status.HTTP_201_CREATED)
async def create_manual_booking(
    body: ServiceBookingCreate,
    _: Annotated[User, Depends(require_admin)],
):
    """Admin-only: create a booking for a cash-paying customer (no Razorpay)."""
    booking = ServiceBooking(
        service_slug=body.service_slug,
        service_name=body.service_name,
        amount=body.amount,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        is_subscription=getattr(body, 'is_subscription', False),
        payment_method=PaymentMethod.cash,
        payment_status=BookingPaymentStatus.unpaid,
        status=BookingStatus.confirmed,
        notes=body.notes,
    )
    await booking.insert()
    return _serialize(booking)
