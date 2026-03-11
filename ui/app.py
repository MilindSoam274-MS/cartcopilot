import json
import uuid
from typing import Any, Dict, Optional

import requests
import streamlit as st

ASSISTANT_BASE = "http://127.0.0.1:8002"
CHECKOUT_BASE = "http://127.0.0.1:8003"


# -----------------------------
# Helpers
# -----------------------------
def post_json(url: str, payload: Dict[str, Any], timeout: int = 20) -> Dict[str, Any]:
    r = requests.post(url, json=payload, timeout=timeout)
    try:
        return r.json()
    except Exception:
        return {"status": "error", "error_code": "NON_JSON_RESPONSE", "message": r.text}


def safe_get(d: Dict[str, Any], key: str, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def format_money(x: Any) -> str:
    try:
        return f"₹{float(x):.0f}" if float(x).is_integer() else f"₹{float(x):.2f}"
    except Exception:
        return str(x)


def ensure_session_id():
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"ui_{uuid.uuid4().hex[:10]}"


def load_cart(session_id: str) -> Dict[str, Any]:
    # Uses your existing assistant-service logic
    return post_json(f"{ASSISTANT_BASE}/chat", {"session_id": session_id, "message": "show cart"})


def start_checkout(session_id: str) -> Dict[str, Any]:
    return post_json(f"{CHECKOUT_BASE}/checkout/start", {"session_id": session_id})


def save_address(session_id: str, address: Dict[str, Any]) -> Dict[str, Any]:
    return post_json(f"{CHECKOUT_BASE}/checkout/address", {"session_id": session_id, "address": address})


def save_payment(session_id: str, payment_method: str) -> Dict[str, Any]:
    return post_json(f"{CHECKOUT_BASE}/checkout/payment", {"session_id": session_id, "payment_method": payment_method})


def confirm_order(session_id: str, confirm: bool) -> Dict[str, Any]:
    return post_json(f"{CHECKOUT_BASE}/checkout/confirm", {"session_id": session_id, "confirm": confirm})


# -----------------------------
# UI State Init
# -----------------------------
st.set_page_config(page_title="CartCopilot UI", page_icon="🛒", layout="wide")
ensure_session_id()

if "last_search" not in st.session_state:
    st.session_state.last_search = None

if "last_add" not in st.session_state:
    st.session_state.last_add = None

if "checkout_state" not in st.session_state:
    st.session_state.checkout_state = None

if "last_checkout_response" not in st.session_state:
    st.session_state.last_checkout_response = None

if "last_order_id" not in st.session_state:
    st.session_state.last_order_id = None


# -----------------------------
# Sidebar: Cart
# -----------------------------
with st.sidebar:
    st.title("🛒 Cart")
    st.caption(f"Session: `{st.session_state.session_id}`")

    if st.button("🔄 Refresh Cart", use_container_width=True):
        st.session_state.last_cart = load_cart(st.session_state.session_id)

    cart_resp = st.session_state.get("last_cart") or load_cart(st.session_state.session_id)
    st.session_state.last_cart = cart_resp

    cart_items = safe_get(cart_resp, "items", []) or safe_get(cart_resp, "cart", [])
    # In your assistant response, cart is usually in "items" for show cart API reply, and also separately in "cart" inside stored session.
    # We'll handle both gracefully.

    if not cart_items:
        st.info("Cart is empty.")
    else:
        total = 0.0
        for it in cart_items:
            name = it.get("item_name", "Item")
            qty = it.get("qty", 1)
            price = it.get("price", 0)
            try:
                total += float(price) * float(qty)
            except Exception:
                pass
            st.write(f"**{name}**")
            st.caption(f"Qty: {qty} · Price: {format_money(price)}")
            st.divider()

        st.subheader(f"Total: {format_money(total)}")

    st.divider()
    st.caption("Services")
    st.write(f"- Assistant: {ASSISTANT_BASE}")
    st.write(f"- Checkout: {CHECKOUT_BASE}")


# -----------------------------
# Main Layout
# -----------------------------
st.title("CartCopilot — Hybrid Food & Grocery AI Assistant")
st.caption("UI orchestrates your existing assistant-service (8002) + checkout-service (8003). No backend logic changes.")

left, right = st.columns([1.3, 1.0], gap="large")


# -----------------------------
# Left: Search + Add
# -----------------------------
with left:
    st.subheader("🔎 Search")

    query = st.text_input(
        "What do you want to eat?",
        value="veg burger under 200 in Bangalore",
        help="This calls assistant-service /chat",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Search", use_container_width=True):
            st.session_state.last_search = post_json(
                f"{ASSISTANT_BASE}/chat",
                {"session_id": st.session_state.session_id, "message": query},
            )
            # refresh cart view after any assistant action
            st.session_state.last_cart = load_cart(st.session_state.session_id)

    with c2:
        if st.button("Show Cart (assistant)", use_container_width=True):
            st.session_state.last_cart = load_cart(st.session_state.session_id)

    if st.session_state.last_search:
        resp = st.session_state.last_search
        st.success("Search response received.")
        st.write(resp.get("reply", ""))

        items = resp.get("items", []) or []
        if items:
            st.markdown("### Results")
            for idx, it in enumerate(items, start=1):
                name = it.get("item_name", "Item")
                price = it.get("price", "")
                cat = it.get("category", "")
                veg = it.get("veg_flag", "")
                st.write(f"**{idx}) {name}** — {format_money(price)} ({veg})")
                if cat:
                    st.caption(f"Category: {cat}")
        else:
            st.info("No items returned from search.")

        st.divider()

    st.subheader("➕ Add to cart (same command style you already support)")
    add_cmd = st.text_input(
        "Add command",
        value="add option 1 x2 and option 3 x1",
        help="We keep your existing text-based add flow (no backend changes).",
    )

    c3, c4 = st.columns([1, 1])
    with c3:
        if st.button("Add", use_container_width=True):
            st.session_state.last_add = post_json(
                f"{ASSISTANT_BASE}/chat",
                {"session_id": st.session_state.session_id, "message": add_cmd},
            )
            st.session_state.last_cart = load_cart(st.session_state.session_id)

    with c4:
        if st.button("Clear UI state", use_container_width=True):
            st.session_state.last_search = None
            st.session_state.last_add = None

    if st.session_state.last_add:
        st.success("Add response received.")
        st.write(st.session_state.last_add.get("reply", ""))
        st.divider()


# -----------------------------
# Right: Checkout State Machine UI
# -----------------------------
with right:
    st.subheader("✅ Checkout")

    # Step indicator (UI only)
    step_map = {
        None: 0,
        "AWAITING_ADDRESS": 1,
        "AWAITING_PAYMENT": 2,
        "CONFIRMING": 3,
        "PLACED": 4,
        "CANCELLED": 4,
    }

    current_state = st.session_state.checkout_state
    st.progress(step_map.get(current_state, 0) / 4 if step_map.get(current_state, 0) <= 4 else 0)

    st.caption(f"Current checkout_state: `{current_state}`")

    if st.button("Proceed to Checkout (start)", use_container_width=True):
        out = start_checkout(st.session_state.session_id)
        st.session_state.last_checkout_response = out
        if out.get("status") == "ok":
            st.session_state.checkout_state = out.get("checkout_state")
        st.session_state.last_cart = load_cart(st.session_state.session_id)

    # Show latest checkout response (debug-friendly)
    if st.session_state.last_checkout_response:
        with st.expander("Latest checkout API response (debug)"):
            st.code(json.dumps(st.session_state.last_checkout_response, indent=2), language="json")

    # Address form shown when state expects address
    if st.session_state.checkout_state == "AWAITING_ADDRESS":
        st.markdown("### 1) Delivery Address")
        with st.form("address_form"):
            name = st.text_input("Name", value="Milind")
            phone = st.text_input("Phone", value="9999999999")
            line1 = st.text_input("Address Line 1", value="SG Palya")
            line2 = st.text_input("Address Line 2 (optional)", value="Near XYZ")
            city = st.text_input("City", value="Bangalore")
            pincode = st.text_input("Pincode", value="560029")
            landmark = st.text_input("Landmark (optional)", value="Near bus stop")
            submitted = st.form_submit_button("Save Address")

        if submitted:
            addr = {
                "name": name,
                "phone": phone,
                "line1": line1,
                "line2": line2 if line2 else None,
                "city": city,
                "pincode": pincode,
                "landmark": landmark if landmark else None,
            }
            out = save_address(st.session_state.session_id, addr)
            st.session_state.last_checkout_response = out
            if out.get("status") == "ok":
                st.session_state.checkout_state = out.get("checkout_state")
            st.rerun()

    # Payment selection
    if st.session_state.checkout_state == "AWAITING_PAYMENT":
        st.markdown("### 2) Payment")
        pm = st.selectbox("Payment method", options=["COD"], index=0)
        if st.button("Save Payment", use_container_width=True):
            out = save_payment(st.session_state.session_id, pm)
            st.session_state.last_checkout_response = out
            if out.get("status") == "ok":
                st.session_state.checkout_state = out.get("checkout_state")
            st.rerun()

    # Confirm screen
    if st.session_state.checkout_state == "CONFIRMING":
        st.markdown("### 3) Confirm Order")
        # If your payment endpoint returns bill in response, show it
        bill = None
        if st.session_state.last_checkout_response:
            bill = st.session_state.last_checkout_response.get("bill")

        if bill:
            st.write("**Bill**")
            st.write(
                f"Subtotal: {format_money(bill.get('subtotal'))}  \n"
                f"Delivery: {format_money(bill.get('delivery_fee'))}  \n"
                f"Grand Total: {format_money(bill.get('grand_total'))}"
            )
        else:
            st.info("Bill will be confirmed on order placement (or check debug response).")

        c5, c6 = st.columns([1, 1])
        with c5:
            if st.button("✅ Place Order", use_container_width=True):
                out = confirm_order(st.session_state.session_id, True)
                st.session_state.last_checkout_response = out
                if out.get("status") == "ok":
                    st.session_state.checkout_state = out.get("checkout_state")
                    st.session_state.last_order_id = out.get("order_id")
                st.rerun()

        with c6:
            if st.button("❌ Cancel", use_container_width=True):
                out = confirm_order(st.session_state.session_id, False)
                st.session_state.last_checkout_response = out
                if out.get("status") == "ok":
                    st.session_state.checkout_state = out.get("checkout_state")
                st.rerun()

    # Receipt screen
    if st.session_state.checkout_state in ("PLACED", "CANCELLED"):
        out = st.session_state.last_checkout_response or {}
        st.markdown("### 4) Result")
        st.success(out.get("message", "Done"))

        if st.session_state.checkout_state == "PLACED":
            st.write(f"**Order ID:** `{out.get('order_id')}`")

        bill = out.get("bill")
        pm = out.get("payment_method")

        if bill:
            st.write("**Bill**")
            st.write(
                f"Subtotal: {format_money(bill.get('subtotal'))}  \n"
                f"Delivery: {format_money(bill.get('delivery_fee'))}  \n"
                f"Grand Total: {format_money(bill.get('grand_total'))}"
            )

        if pm:
            st.write(f"**Payment:** `{pm}`")

        if st.button("Start New Session (new session_id)", use_container_width=True):
            st.session_state.session_id = f"ui_{uuid.uuid4().hex[:10]}"
            st.session_state.last_search = None
            st.session_state.last_add = None
            st.session_state.checkout_state = None
            st.session_state.last_checkout_response = None
            st.session_state.last_order_id = None
            st.session_state.last_cart = None
            st.rerun()