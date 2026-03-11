from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime
import uuid

from prometheus_client import Counter

from .redis_store import (
    get_json,
    load_checkout,
    save_checkout,
    save_order,
    save_last_order,
    session_key,
)
from .config import CHECKOUT_TTL_SECONDS


# =========================
# Business Metrics (Prometheus)
# =========================
CHECKOUT_START_ATTEMPTS_TOTAL = Counter(
    "checkout_start_attempts_total",
    "Total attempts to start checkout",
)

CHECKOUT_START_FAILED_TOTAL = Counter(
    "checkout_start_failed_total",
    "Total failed checkout starts",
    ["reason"],  # CART_EMPTY, CART_INVALID, etc.
)

CHECKOUT_STARTED_TOTAL = Counter(
    "checkout_started_total",
    "Total successful checkout starts (state moved to AWAITING_ADDRESS)",
)

CHECKOUT_INVALID_TRANSITION_TOTAL = Counter(
    "checkout_invalid_transition_total",
    "Total invalid state transitions attempted",
    ["action", "state"],  # action=address/payment/confirm, state=current state
)

CHECKOUT_ADDRESS_SAVED_TOTAL = Counter(
    "checkout_address_saved_total",
    "Total times address step was successfully completed",
)

CHECKOUT_PAYMENT_SAVED_TOTAL = Counter(
    "checkout_payment_saved_total",
    "Total times payment step was successfully completed",
)

CHECKOUT_CANCELLED_TOTAL = Counter(
    "checkout_cancelled_total",
    "Total checkouts cancelled by user (confirm=false)",
)

ORDERS_PLACED_TOTAL = Counter(
    "orders_placed_total",
    "Total orders successfully placed",
)

CHECKOUT_IDEMPOTENT_HITS_TOTAL = Counter(
    "checkout_idempotent_hits_total",
    "Total idempotent calls (e.g., confirm called after already placed, start called when already placed)",
    ["action"],  # start/confirm/address/payment
)


# ---- States ----
AWAITING_ADDRESS = "AWAITING_ADDRESS"
AWAITING_PAYMENT = "AWAITING_PAYMENT"
CONFIRMING = "CONFIRMING"
PLACED = "PLACED"
CANCELLED = "CANCELLED"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _validate_cart(cart: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if not cart:
        return False, "Cart is empty"

    for i, it in enumerate(cart, start=1):
        try:
            price = float(it.get("price"))
            qty = int(it.get("qty"))
        except Exception:
            return False, f"Invalid cart item at position {i}"

        if price <= 0:
            return False, f"Invalid price at cart item {i}"
        if qty < 1:
            return False, f"Invalid qty at cart item {i}"

    return True, ""


def _compute_bill(cart: List[Dict[str, Any]]) -> Dict[str, float]:
    subtotal = 0.0
    for it in cart:
        price = float(it.get("price") or 0)
        qty = int(it.get("qty") or 1)
        subtotal += price * qty

    # Delivery Fee Rule C
    delivery_fee = 20.0 if subtotal < 199 else 0.0
    grand_total = subtotal + delivery_fee

    return {"subtotal": round(subtotal, 2), "delivery_fee": delivery_fee, "grand_total": round(grand_total, 2)}


def _cart_view(cart: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for it in cart:
        out.append(
            {
                "item_id": it.get("item_id"),
                "item_name": it.get("item_name"),
                "price": float(it.get("price") or 0),
                "qty": int(it.get("qty") or 1),
                "restaurant_id": it.get("restaurant_id"),
                "city": it.get("city"),
                "veg_flag": it.get("veg_flag"),
            }
        )
    return out


def start_checkout(session_id: str) -> Dict[str, Any]:
    """
    Reads assistant session state from Redis key = session_id
    Freezes cart into checkout:{session_id}
    Computes bill, moves to AWAITING_ADDRESS
    """
    CHECKOUT_START_ATTEMPTS_TOTAL.inc()

    # 1) Read assistant session state
    mem = get_json(session_key(session_id)) or {}
    cart = mem.get("cart") or []

    ok, reason = _validate_cart(cart)
    if not ok:
        # Business metric: why start failed
        if not cart:
            CHECKOUT_START_FAILED_TOTAL.labels(reason="CART_EMPTY").inc()
            return {"ok": False, "error_code": "CART_EMPTY", "message": reason}
        else:
            CHECKOUT_START_FAILED_TOTAL.labels(reason="CART_INVALID").inc()
            return {"ok": False, "error_code": "CART_INVALID", "message": reason}

    # 2) If checkout already placed, be idempotent
    existing = load_checkout(session_id) or {}
    if existing.get("state") == PLACED and existing.get("order_id"):
        CHECKOUT_IDEMPOTENT_HITS_TOTAL.labels(action="start").inc()
        return {
            "ok": True,
            "checkout_state": PLACED,
            "cart": _cart_view(existing.get("cart_snapshot") or []),
            "bill": existing.get("bill") or _compute_bill(cart),
            "message": "Order already placed",
            "order_id": existing.get("order_id"),
        }

    # 3) Create/overwrite checkout session (freeze snapshot)
    bill = _compute_bill(cart)
    payload = {
        "session_id": session_id,
        "state": AWAITING_ADDRESS,
        "created_at": existing.get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
        "cart_snapshot": _cart_view(cart),
        "bill": bill,
        "address": existing.get("address"),  # keep if exists
        "payment_method": existing.get("payment_method"),
        "order_id": existing.get("order_id"),
    }

    save_checkout(session_id, payload)

    # Business metric: successful start
    CHECKOUT_STARTED_TOTAL.inc()

    return {
        "ok": True,
        "checkout_state": AWAITING_ADDRESS,
        "cart": payload["cart_snapshot"],
        "bill": bill,
        "next_action": "Provide delivery address via /checkout/address",
    }


def save_address(session_id: str, address: Dict[str, Any]) -> Dict[str, Any]:
    chk = load_checkout(session_id) or {}
    if not chk:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="address", state="NOT_STARTED").inc()
        return {"ok": False, "error_code": "CHECKOUT_NOT_STARTED", "message": "Start checkout first using /checkout/start"}

    state = chk.get("state")
    if state == PLACED:
        CHECKOUT_IDEMPOTENT_HITS_TOTAL.labels(action="address").inc()
        return {"ok": True, "checkout_state": PLACED, "message": "Order already placed", "order_id": chk.get("order_id")}
    if state == CANCELLED:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="address", state=CANCELLED).inc()
        return {"ok": False, "error_code": "CHECKOUT_CANCELLED", "message": "Checkout is cancelled. Start again with /checkout/start", "checkout_state": CANCELLED}
    if state not in (AWAITING_ADDRESS,):
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="address", state=str(state)).inc()
        return {"ok": False, "error_code": "INVALID_STATE", "message": f"Address not allowed in state {state}", "checkout_state": state}

    chk["address"] = address
    chk["state"] = AWAITING_PAYMENT
    chk["updated_at"] = _now_iso()
    save_checkout(session_id, chk)

    CHECKOUT_ADDRESS_SAVED_TOTAL.inc()

    return {"ok": True, "checkout_state": AWAITING_PAYMENT, "message": "Address saved. Choose payment method via /checkout/payment"}


def save_payment(session_id: str, payment_method: str) -> Dict[str, Any]:
    chk = load_checkout(session_id) or {}
    if not chk:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="payment", state="NOT_STARTED").inc()
        return {"ok": False, "error_code": "CHECKOUT_NOT_STARTED", "message": "Start checkout first using /checkout/start"}

    state = chk.get("state")
    if state == PLACED:
        CHECKOUT_IDEMPOTENT_HITS_TOTAL.labels(action="payment").inc()
        return {"ok": True, "checkout_state": PLACED, "message": "Order already placed", "order_id": chk.get("order_id")}
    if state == CANCELLED:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="payment", state=CANCELLED).inc()
        return {"ok": False, "error_code": "CHECKOUT_CANCELLED", "message": "Checkout is cancelled. Start again with /checkout/start", "checkout_state": CANCELLED}
    if state not in (AWAITING_PAYMENT,):
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="payment", state=str(state)).inc()
        return {"ok": False, "error_code": "INVALID_STATE", "message": f"Payment not allowed in state {state}", "checkout_state": state}

    chk["payment_method"] = payment_method
    chk["state"] = CONFIRMING
    chk["updated_at"] = _now_iso()
    save_checkout(session_id, chk)

    CHECKOUT_PAYMENT_SAVED_TOTAL.inc()

    return {
        "ok": True,
        "checkout_state": CONFIRMING,
        "payment_method": payment_method,
        "bill": chk.get("bill"),
        "message": "Confirm order via /checkout/confirm with confirm=true/false",
    }


def confirm_checkout(session_id: str, confirm: bool) -> Dict[str, Any]:
    chk = load_checkout(session_id) or {}
    if not chk:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="confirm", state="NOT_STARTED").inc()
        return {"ok": False, "error_code": "CHECKOUT_NOT_STARTED", "message": "Start checkout first using /checkout/start"}

    state = chk.get("state")
    if state == PLACED and chk.get("order_id"):
        CHECKOUT_IDEMPOTENT_HITS_TOTAL.labels(action="confirm").inc()
        return {
            "ok": True,
            "checkout_state": PLACED,
            "message": "Order already placed",
            "bill": chk.get("bill"),
            "payment_method": chk.get("payment_method"),
            "order_id": chk.get("order_id"),
        }

    if state == CANCELLED:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="confirm", state=CANCELLED).inc()
        return {"ok": False, "error_code": "CHECKOUT_CANCELLED", "message": "Checkout is cancelled. Start again with /checkout/start", "checkout_state": CANCELLED}

    if state != CONFIRMING:
        CHECKOUT_INVALID_TRANSITION_TOTAL.labels(action="confirm", state=str(state)).inc()
        return {"ok": False, "error_code": "INVALID_STATE", "message": f"Confirm not allowed in state {state}", "checkout_state": state}

    if not confirm:
        chk["state"] = CANCELLED
        chk["updated_at"] = _now_iso()
        save_checkout(session_id, chk)

        CHECKOUT_CANCELLED_TOTAL.inc()

        return {"ok": True, "checkout_state": CANCELLED, "message": "Checkout cancelled"}

    # Place order
    order_id = chk.get("order_id") or f"ord_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    order_obj = {
        "order_id": order_id,
        "session_id": session_id,
        "placed_at": _now_iso(),
        "status": "PLACED",
        "cart": chk.get("cart_snapshot") or [],
        "bill": chk.get("bill") or {},
        "address": chk.get("address"),
        "payment_method": chk.get("payment_method"),
    }

    save_order(order_id, order_obj)
    save_last_order(session_id, order_id)

    chk["state"] = PLACED
    chk["order_id"] = order_id
    chk["updated_at"] = _now_iso()
    save_checkout(session_id, chk)

    ORDERS_PLACED_TOTAL.inc()

    return {
        "ok": True,
        "checkout_state": PLACED,
        "order_id": order_id,
        "bill": order_obj["bill"],
        "payment_method": order_obj["payment_method"],
        "message": "Order placed successfully",
    }