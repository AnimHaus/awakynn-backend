from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user, get_optional_user, require_admin
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate, PaymentVerify, OrderTrackOut, TrackByEmailRequest

router = APIRouter(prefix="/orders", tags=["orders"])

SHIPPING_THRESHOLD = 500.0
SHIPPING_FEE = 49.0


def _serialize(o: Order) -> dict:
    return {
        "id": str(o.id),
        "user_id": o.user_id,
        "guest_email": o.guest_email,
        "items": o.items,
        "subtotal": o.subtotal,
        "shipping_fee": o.shipping_fee,
        "total": o.total,
        "status": o.status,
        "payment_status": o.payment_status,
        "shipping_address": o.shipping_address,
        "razorpay_order_id": o.razorpay_order_id,
        "razorpay_invoice_id": o.razorpay_invoice_id,
        "notes": o.notes,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    current_user: Annotated[Optional[User], Depends(get_optional_user)] = None,
):
    # Validate products and calculate subtotal
    items_out = []
    subtotal = 0.0

    for item in body.items:
        product = await Product.find_one(Product.slug == item.slug, Product.is_active == True)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{item.slug}' not found or unavailable",
            )
        # Match SKU price
        sku_match = next((s for s in product.pricing if s["label"] == item.sku_label), None)
        if not sku_match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SKU '{item.sku_label}' not found for product '{item.slug}'",
            )
        line_total = sku_match["price"] * item.quantity
        subtotal += line_total
        items_out.append({
            "product_id": str(product.id),
            "slug": product.slug,
            "name": product.name,
            "sku_label": item.sku_label,
            "quantity": item.quantity,
            "unit_price": sku_match["price"],
        })

    shipping_fee = 0.0 if subtotal >= SHIPPING_THRESHOLD else SHIPPING_FEE
    total = subtotal + shipping_fee

    order = Order(
        user_id=str(current_user.id) if current_user else None,
        guest_email=body.guest_email if not current_user else None,
        items=items_out,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        shipping_address=body.shipping_address.model_dump(),
        notes=body.notes,
    )
    await order.insert()
    return _serialize(order)


@router.get("/me", response_model=List[OrderOut])
async def my_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
):
    orders = (
        await Order.find(Order.user_id == str(current_user.id))
        .sort(-Order.created_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    return [_serialize(o) for o in orders]


# ── Public tracking endpoints (no auth required) ─────────────────────────────

def _mask_email(email: str) -> str:
    """Return e.g. 'jo***@gmail.com' so the customer can confirm it's theirs."""
    try:
        local, domain = email.split("@", 1)
        visible = local[:2] if len(local) >= 2 else local[:1]
        return f"{visible}***@{domain}"
    except ValueError:
        return "***"


def _serialize_track(o: Order) -> dict:
    email = o.guest_email or ""
    return {
        "id": str(o.id),
        "razorpay_order_id": o.razorpay_order_id,
        "items": o.items,
        "subtotal": o.subtotal,
        "shipping_fee": o.shipping_fee,
        "total": o.total,
        "status": o.status,
        "payment_status": o.payment_status,
        "shipping_address": o.shipping_address,
        "notes": o.notes,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "masked_email": _mask_email(email) if email else None,
    }


@router.get("/track/{order_id}", response_model=OrderTrackOut)
async def track_order_by_id(order_id: str):
    """Public endpoint — accepts a MongoDB ObjectId OR a Razorpay order ID (order_…)."""
    if order_id.startswith("order_"):
        order = await Order.find_one(Order.razorpay_order_id == order_id)
    else:
        order = await Order.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return _serialize_track(order)


@router.post("/track/by-email", response_model=List[OrderTrackOut])
async def track_orders_by_email(body: TrackByEmailRequest):
    """Public endpoint — returns all guest orders matching the supplied email."""
    # Normalise to lowercase to avoid case-sensitivity issues
    email = body.email.strip().lower()
    orders = (
        await Order.find(Order.guest_email == email)
        .sort(-Order.created_at)
        .limit(20)
        .to_list()
    )
    return [_serialize_track(o) for o in orders]



async def get_order(
    order_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    order = await Order.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not current_user.is_admin and order.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _serialize(order)


# ── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("/", response_model=List[OrderOut])
async def list_all_orders(
    _: Annotated[User, Depends(require_admin)],
    status_filter: Optional[OrderStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = Order.find(Order.status == status_filter) if status_filter else Order.find()
    orders = await query.sort(-Order.created_at).skip(skip).limit(limit).to_list()
    return [_serialize(o) for o in orders]


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    _: Annotated[User, Depends(require_admin)],
):
    order = await Order.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    await order.set({"status": body.status})
    return _serialize(order)


@router.post("/{order_id}/razorpay-order", response_model=dict)
async def create_razorpay_order(order_id: str):
    """Create a Razorpay order for an existing backend order and persist razorpay_order_id."""
    import razorpay
    from app.config import settings

    order = await Order.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    rz_order = client.order.create({
        "amount": int(order.total * 100),  # paise
        "currency": "INR",
        "receipt": str(order.id),
        "payment_capture": 1,
    })

    await order.set({"razorpay_order_id": rz_order["id"]})
    return {
        "razorpay_order_id": rz_order["id"],
        "amount": rz_order["amount"],
        "currency": rz_order["currency"],
        "key_id": settings.RAZORPAY_KEY_ID,
    }


@router.post("/{order_id}/verify-payment", response_model=OrderOut)
async def verify_payment(
    order_id: str,
    body: PaymentVerify,
    current_user: Annotated[Optional[User], Depends(get_optional_user)] = None,
):
    import hashlib
    import hmac
    from app.config import settings
    from app.services.invoice import create_invoice

    order = await Order.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Verify Razorpay signature
    msg = f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")

    await order.set({
        "payment_status": PaymentStatus.paid,
        "status": OrderStatus.confirmed,
        "razorpay_payment_id": body.razorpay_payment_id,
    })

    # Deduct stock for each item purchased
    for item in order.items:
        product = await Product.find_one(Product.slug == item["slug"])
        if product and product.stock > 0:
            new_stock = max(0, product.stock - item["quantity"])
            await product.set({"stock": new_stock})

    # Generate and issue Razorpay invoice automatically
    addr = order.shipping_address or {}
    invoice_id = create_invoice(
        order_id=str(order.id),
        razorpay_order_id=body.razorpay_order_id,
        items=order.items,
        shipping_fee=order.shipping_fee,
        customer_name=addr.get("full_name") or (current_user.name if current_user else "Customer"),
        customer_email=order.guest_email or (current_user.email if current_user else None),
        customer_phone=addr.get("phone") or (current_user.phone if current_user and hasattr(current_user, "phone") else None),
        shipping_address=addr,
    )
    if invoice_id:
        await order.set({"razorpay_invoice_id": invoice_id})

    return _serialize(order)
