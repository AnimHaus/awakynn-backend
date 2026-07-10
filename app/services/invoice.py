"""
Razorpay invoice automation service.

After a payment is verified, call `create_invoice` to generate and
issue a Razorpay invoice that is e-mailed / SMS'd to the customer.
The invoice reuses the pre-created Razorpay items so that line-item
details (name, description, unit_amount) are pulled directly from the
Razorpay dashboard without duplication.

Item ID mapping (slug :: sku_label → Razorpay item_id):
  snowball-coco :: Pack of 8       → item_TBt0jGImP1jlpU
  fruit-gels    :: 30g             → item_TBt0HASFggLar0
  makhana       :: 20g             → item_TBszmEfeDUf31W
  loaf          :: Buckwheat Loaf  → item_TBsyecXR0QxLvO
  loaf          :: Flax Loaf       → item_TBsxy4298VLm7z
  bites         :: Single          → item_TBsxLSYqnbZyux
  bites         :: Pack of 4       → item_TBswoQGgEa6w11
  peanut-butter :: 30g             → item_TBsunJWxq1kGHr
  muesli        :: 35g             → item_TBsuGkNY2uOTST
  muesli        :: 100g            → item_TBstJRb3hmhj4O
"""

import logging
import time
from typing import Optional

import razorpay

from app.config import settings

logger = logging.getLogger(__name__)

# ── Item ID lookup ────────────────────────────────────────────────────────────
# Key: "<slug>::<sku_label>"  (case-sensitive, matches values stored in Order.items)
RAZORPAY_ITEM_MAP: dict[str, str] = {
    "snowball-coco::Pack of 8":      "item_TBt0jGImP1jlpU",
    "fruit-gels::30g":               "item_TBt0HASFggLar0",
    "makhana::20g":                  "item_TBszmEfeDUf31W",
    "loaf::Buckwheat Loaf":          "item_TBsyecXR0QxLvO",
    "loaf::Flax Loaf":               "item_TBsxy4298VLm7z",
    "bites::Single":                 "item_TBsxLSYqnbZyux",
    "bites::Pack of 4":              "item_TBswoQGgEa6w11",
    "peanut-butter::30g":            "item_TBsunJWxq1kGHr",
    "muesli::35g":                   "item_TBsuGkNY2uOTST",
    "muesli::100g":                  "item_TBstJRb3hmhj4O",
}


def _get_client() -> razorpay.Client:
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def create_invoice(
    *,
    order_id: str,
    razorpay_order_id: str,
    items: list[dict],
    shipping_fee: float,
    customer_name: str,
    customer_email: Optional[str],
    customer_phone: Optional[str],
    shipping_address: dict,
) -> Optional[str]:
    """
    Create and issue a Razorpay invoice for a confirmed order.

    Returns the Razorpay invoice ID (``inv_xxx``) on success, or ``None``
    if invoice creation is not possible (e.g. no Razorpay credentials
    configured, or an unmapped SKU is encountered).

    Errors are logged rather than raised so that a billing failure never
    blocks the payment-confirmation response to the customer.
    """
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        logger.warning("Invoice skipped: Razorpay credentials not configured.")
        return None

    # Build line_items list
    line_items: list[dict] = []
    for item in items:
        key = f"{item.get('slug', '')}::{item.get('sku_label', '')}"
        item_id = RAZORPAY_ITEM_MAP.get(key)
        if not item_id:
            logger.warning(
                "Invoice: no Razorpay item_id for key=%r (order %s). "
                "Falling back to inline line item.",
                key,
                order_id,
            )
            # Fallback: inline line item without a pre-created item_id
            line_items.append({
                "name": item.get("name", key),
                "description": item.get("sku_label", ""),
                "amount": int(item.get("unit_price", 0) * 100),  # paise
                "currency": "INR",
                "quantity": item.get("quantity", 1),
            })
        else:
            line_items.append({
                "item_id": item_id,
                "quantity": item.get("quantity", 1),
            })

    if not line_items:
        logger.warning("Invoice skipped: no line items for order %s.", order_id)
        return None

    # Optionally add shipping as a separate line item
    if shipping_fee and shipping_fee > 0:
        line_items.append({
            "name": "Shipping",
            "description": "Delivery charges",
            "amount": int(shipping_fee * 100),
            "currency": "INR",
            "quantity": 1,
        })

    # Build customer object
    customer: dict = {"name": customer_name}
    if customer_email:
        customer["email"] = customer_email
    if customer_phone:
        customer["contact"] = customer_phone

    addr = shipping_address or {}
    if addr:
        customer["billing_address"] = {
            "line1": addr.get("line1", ""),
            "line2": addr.get("line2", ""),
            "city": addr.get("city", ""),
            "state": addr.get("state", ""),
            "zipcode": addr.get("pincode", ""),
            "country": addr.get("country", "India"),
        }

    invoice_payload: dict = {
        "type": "invoice",
        "description": f"Grabfabs Order #{order_id}",
        "customer": customer,
        "line_items": line_items,
        "date": int(time.time()),
        # Invoice expires 7 days from now (informational; already paid)
        "expire_by": int(time.time()) + 7 * 24 * 3600,
        "sms_notify": 1 if customer_phone else 0,
        "email_notify": 1 if customer_email else 0,
        "currency": "INR",
        # Link this invoice to the existing Razorpay order
        "order_id": razorpay_order_id,
    }

    try:
        client = _get_client()
        invoice = client.invoice.create(invoice_payload)
        invoice_id: str = invoice["id"]

        # Issue (send) the invoice immediately so the customer receives it
        client.invoice.issue(invoice_id)

        logger.info(
            "Invoice %s created and issued for order %s.", invoice_id, order_id
        )
        return invoice_id

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to create Razorpay invoice for order %s: %s",
            order_id,
            exc,
            exc_info=True,
        )
        return None
