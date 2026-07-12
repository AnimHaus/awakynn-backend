"""
Razorpay webhook handler.

Register this URL in the Razorpay dashboard:
  POST https://<your-api-domain>/api/v1/webhooks/razorpay

Enable the following events:
  ── Grabfabs orders (one-time payments) ────────────────────────────────────
  • payment.captured       ← primary: fired when any payment is captured
  • order.paid             ← fallback: fired when an order is fully paid

  ── Awakynn service bookings (one-time) ────────────────────────────────────
  • payment.captured       ← same event, differentiated by presence of order_id
  • order.paid             ← same event

  ── Awakynn subscriptions (recurring) ─────────────────────────────────────
  • subscription.activated ← first payment collected, subscription is live
  • subscription.charged   ← EVERY recurring charge (most important)
  • subscription.completed ← all billing cycles finished
  • subscription.cancelled ← customer / admin cancelled the subscription
  • subscription.halted    ← payment failed after all retries; requires action

Set the webhook secret in your .env as RAZORPAY_WEBHOOK_SECRET.

Why this is needed
──────────────────
On mobile browsers, UPI apps (GPay, PhonePe, Paytm …) switch the user
out of the browser tab to complete payment. The Razorpay JS handler
callback is often never called, leaving the order as "unpaid" in the
DB even though Razorpay received the funds. Webhooks are delivered
server-to-server and are the authoritative source of payment truth.
"""

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.product import Product
from app.models.service_booking import BookingPaymentStatus, BookingStatus, ServiceBooking

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_signature(body: bytes, header_sig: str) -> bool:
    """Validate X-Razorpay-Signature using HMAC-SHA256."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        logger.warning("RAZORPAY_WEBHOOK_SECRET is not configured — skipping signature check")
        return True  # Allow in dev; tighten in production by returning False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig)


# ── Grabfabs order confirmation ───────────────────────────────────────────────

async def _confirm_order_by_razorpay_id(
    razorpay_order_id: str,
    razorpay_payment_id: Optional[str],
) -> None:
    """
    Look up the internal order by razorpay_order_id, confirm it if not
    already paid, deduct stock, and issue an invoice.
    Idempotent — safe to call multiple times for the same event.
    """
    order = await Order.find_one(Order.razorpay_order_id == razorpay_order_id)
    if not order:
        logger.warning("Webhook: no order found for razorpay_order_id=%s", razorpay_order_id)
        return

    if order.payment_status == PaymentStatus.paid:
        logger.info("Webhook: order %s already marked paid, skipping", order.id)
        return

    updates: dict = {
        "payment_status": PaymentStatus.paid,
        "status": OrderStatus.confirmed,
    }
    if razorpay_payment_id:
        updates["razorpay_payment_id"] = razorpay_payment_id

    await order.set(updates)
    logger.info("Webhook: confirmed order %s (razorpay_order_id=%s)", order.id, razorpay_order_id)

    for item in order.items:
        product = await Product.find_one(Product.slug == item["slug"])
        if product and product.stock > 0:
            new_stock = max(0, product.stock - item["quantity"])
            await product.set({"stock": new_stock})

    try:
        from app.services.invoice import create_invoice

        addr = order.shipping_address or {}
        invoice_id = create_invoice(
            order_id=str(order.id),
            razorpay_order_id=razorpay_order_id,
            items=order.items,
            shipping_fee=order.shipping_fee,
            customer_name=addr.get("full_name") or "Customer",
            customer_email=order.guest_email,
            customer_phone=addr.get("phone"),
            shipping_address=addr,
        )
        if invoice_id:
            await order.set({"razorpay_invoice_id": invoice_id})
    except Exception as exc:
        logger.error("Webhook: invoice creation failed for order %s: %s", order.id, exc)


# ── Awakynn service booking (one-time) confirmation ──────────────────────────

async def _confirm_booking_by_razorpay_order_id(
    razorpay_order_id: str,
    razorpay_payment_id: Optional[str],
) -> None:
    """Confirm a one-time service booking via its Razorpay order ID."""
    booking = await ServiceBooking.find_one(
        ServiceBooking.razorpay_order_id == razorpay_order_id,
        ServiceBooking.is_subscription == False,
    )
    if not booking:
        return  # Not a service booking — that's fine, probably a Grabfabs order

    if booking.payment_status == BookingPaymentStatus.paid:
        logger.info("Webhook: booking %s already paid, skipping", booking.id)
        return

    updates: dict = {
        "payment_status": BookingPaymentStatus.paid,
        "status": BookingStatus.confirmed,
    }
    if razorpay_payment_id:
        updates["razorpay_payment_id"] = razorpay_payment_id

    await booking.set(updates)
    logger.info("Webhook: confirmed booking %s (razorpay_order_id=%s)", booking.id, razorpay_order_id)


# ── Awakynn subscription events ───────────────────────────────────────────────

async def _handle_subscription_event(event: str, subscription_entity: dict, payment_entity: Optional[dict]) -> None:
    """Handle all subscription.* webhook events."""
    razorpay_subscription_id = subscription_entity.get("id")
    if not razorpay_subscription_id:
        return

    booking = await ServiceBooking.find_one(
        ServiceBooking.razorpay_subscription_id == razorpay_subscription_id
    )
    if not booking:
        logger.warning("Webhook: no booking found for subscription_id=%s", razorpay_subscription_id)
        return

    razorpay_payment_id = (payment_entity or {}).get("id")

    if event == "subscription.activated":
        # First charge collected — subscription is now live
        if booking.payment_status != BookingPaymentStatus.paid:
            updates: dict = {
                "payment_status": BookingPaymentStatus.paid,
                "status": BookingStatus.confirmed,
            }
            if razorpay_payment_id:
                updates["razorpay_payment_id"] = razorpay_payment_id
            await booking.set(updates)
            logger.info("Webhook: subscription %s activated for booking %s", razorpay_subscription_id, booking.id)

    elif event == "subscription.charged":
        # Recurring charge collected — keep booking confirmed & update latest payment ID
        updates = {"payment_status": BookingPaymentStatus.paid, "status": BookingStatus.confirmed}
        if razorpay_payment_id:
            updates["razorpay_payment_id"] = razorpay_payment_id
        await booking.set(updates)
        logger.info("Webhook: subscription %s charged for booking %s", razorpay_subscription_id, booking.id)

    elif event == "subscription.completed":
        # All billing cycles finished
        await booking.set({"status": BookingStatus.completed})
        logger.info("Webhook: subscription %s completed for booking %s", razorpay_subscription_id, booking.id)

    elif event == "subscription.cancelled":
        await booking.set({"status": BookingStatus.cancelled})
        logger.info("Webhook: subscription %s cancelled for booking %s", razorpay_subscription_id, booking.id)

    elif event == "subscription.halted":
        # Payment failed after all retries — flag it so admin can follow up
        await booking.set({
            "payment_status": BookingPaymentStatus.unpaid,
            "status": BookingStatus.cancelled,
        })
        logger.warning("Webhook: subscription %s HALTED for booking %s — payment failed", razorpay_subscription_id, booking.id)


# ── Main webhook endpoint ─────────────────────────────────────────────────────

@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request):
    """
    Razorpay sends a POST with JSON body and the header
    X-Razorpay-Signature containing the HMAC-SHA256 of the raw body.
    We must read the raw body for signature verification BEFORE parsing JSON.
    """
    raw_body = await request.body()

    sig_header = request.headers.get("X-Razorpay-Signature", "")
    if not _verify_signature(raw_body, sig_header):
        logger.warning("Webhook: invalid signature — rejecting request")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event = payload.get("event", "")
    logger.info("Webhook received: event=%s", event)

    # ── payment.captured ─────────────────────────────────────────────────────
    # Fired for both order-based and subscription payments.
    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_order_id = payment.get("order_id")
        razorpay_payment_id = payment.get("id")
        if razorpay_order_id:
            # Try Grabfabs order first, then Awakynn one-time booking
            await _confirm_order_by_razorpay_id(razorpay_order_id, razorpay_payment_id)
            await _confirm_booking_by_razorpay_order_id(razorpay_order_id, razorpay_payment_id)

    # ── order.paid ───────────────────────────────────────────────────────────
    elif event == "order.paid":
        order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_order_id = order_entity.get("id")
        razorpay_payment_id = payment_entity.get("id")
        if razorpay_order_id:
            await _confirm_order_by_razorpay_id(razorpay_order_id, razorpay_payment_id)
            await _confirm_booking_by_razorpay_order_id(razorpay_order_id, razorpay_payment_id)

    # ── subscription.* ───────────────────────────────────────────────────────
    elif event.startswith("subscription."):
        subscription_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity")
        await _handle_subscription_event(event, subscription_entity, payment_entity)

    # Return 200 for all events — Razorpay retries on any non-2xx response.
    return {"received": True}
