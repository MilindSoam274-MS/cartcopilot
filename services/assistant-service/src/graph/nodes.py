import re
from typing import Any, Dict, List, Tuple
from .schema import AssistantState

from ..intent import detect_intent
from ..retrieval_client import retrieve_items
from ..llm import generate_response


def _parse_option_numbers(text: str) -> List[int]:
    """
    Extract ONE or MANY option numbers from user text (multi-add case).

    Examples:
    - "add option 2" -> [2]
    - "add 1 and 3" -> [1, 3]
    - "add option 1,3,5" -> [1,3,5]
    """
    nums = re.findall(r"\b\d+\b", (text or "").lower())
    out: List[int] = []
    seen = set()
    for n in nums:
        try:
            v = int(n)
            if v not in seen:
                out.append(v)
                seen.add(v)
        except Exception:
            continue
    return out


def _parse_add_requests(text: str, max_option: int) -> List[Tuple[int, int]]:
    """
    Step 5E.4: multi-quantity parser.

    Returns list of (option_number, qty).

    Supported patterns (MULTI in one sentence):
    - "add 2 of option 1 and 1 of option 4"     -> [(1,2),(4,1)]
    - "add option 2 x3, option 5 x1"            -> [(2,3),(5,1)]
    - "add 1x2 and 3x1"                         -> [(1,2),(3,1)]
    - "add option 4 twice"                      -> [(4,2)]

    Also supports mixing qty patterns + plain options:
    - "add 2 of option 1 and 3"                 -> [(1,2),(3,1)]
      (because 3 is a plain option, qty defaults to 1)

    Safety:
    - option must be 1..max_option
    - qty must be >= 1
    - if same option appears multiple times, we SUM qty
    """
    msg = (text or "").lower().strip()

    accum: Dict[int, int] = {}

    # Pattern A: "2 of option 1"  (qty first, option second)
    for m in re.finditer(r"\b(\d+)\s+(?:of\s+)?(?:option\s*)?(\d+)\b", msg):
        qty = int(m.group(1))
        opt = int(m.group(2))
        if 1 <= opt <= max_option and qty >= 1:
            accum[opt] = accum.get(opt, 0) + qty

    # Pattern B: "option 3 x2" or "3x2" (option first, qty second)
    for m in re.finditer(r"\b(?:option\s*)?(\d+)\s*(?:x|×|\*)\s*(\d+)\b", msg):
        opt = int(m.group(1))
        qty = int(m.group(2))
        if 1 <= opt <= max_option and qty >= 1:
            accum[opt] = accum.get(opt, 0) + qty

    # Pattern C: "option 4 twice"
    for m in re.finditer(r"\b(?:option\s*)?(\d+)\s+twice\b", msg):
        opt = int(m.group(1))
        if 1 <= opt <= max_option:
            accum[opt] = accum.get(opt, 0) + 2

    # If we found any qty-patterns, also include plain options (qty=1)
    # that appear in the message but were not captured above.
    if accum:
        plain_opts = _parse_option_numbers(msg)
        for opt in plain_opts:
            if 1 <= opt <= max_option and opt not in accum:
                accum[opt] = 1

    # Return in stable order by option number (helps predictable testing)
    return [(opt, accum[opt]) for opt in sorted(accum.keys())]


def _cart_total(cart: List[Dict[str, Any]]) -> float:
    total = 0.0
    for x in cart:
        price = float(x.get("price") or 0)
        qty = int(x.get("qty") or 1)
        total += price * qty
    return total


def _pick_cheapest(items: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not items:
        return None
    return min(items, key=lambda x: float(x.get("price") or 1e18))


def _pick_most_expensive(items: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda x: float(x.get("price") or -1))


def _pick_best(items: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """
    "Best" for now = highest similarity score returned by retrieval.
    (Later we can incorporate rating, rating_count, etc.)
    """
    if not items:
        return None
    return max(items, key=lambda x: float(x.get("score") or -1e18))


def intent_node(state: AssistantState) -> Dict[str, Any]:
    intent = detect_intent(state["user_message"])
    print("Detected Intent:", intent)
    return {"intent": intent}


def set_next_refine(state: AssistantState) -> Dict[str, Any]:
    return {"_next_node": "refine_node"}


def set_next_compare(state: AssistantState) -> Dict[str, Any]:
    return {"_next_node": "compare_node"}


def set_next_addons(state: AssistantState) -> Dict[str, Any]:
    return {"_next_node": "addons_node"}


def guard_node(state: AssistantState) -> Dict[str, Any]:
    """
    Guard for follow-up turns (refine/compare/add-ons/cart add).
    """
    last_items = state.get("last_items") or []
    last_results = state.get("last_results") or []

    # For cart add/remove, last_results is what matters
    if state.get("intent") in ("ADD_TO_CART", "REMOVE_FROM_CART"):
        if not last_results and not (state.get("cart") or []):
            return {
                "halt": True,
                "items": [],
                "confidence": "low",
                "reply": "I don’t have any recent results yet. Please search first (e.g., 'veg burger under 200 in Bangalore').",
            }
        return {"halt": False}

    if state.get("intent") in ("REFINE_CHEAP", "REFINE_BEST", "COMPARE", "ADD_ONS"):
        if not last_items:
            return {
                "halt": True,
                "items": [],
                "confidence": "low",
                "reply": "I don’t have any results yet. Please search first (e.g., 'veg burger under 200 in Bangalore').",
            }
        return {"halt": False}

    return {"halt": False}


def search_node(state: AssistantState) -> Dict[str, Any]:
    payload = {
        "query": state["user_message"],
        "city": state.get("city"),
        "veg_flag": state.get("veg_flag"),
        "max_price": state.get("max_price"),
    }

    r = retrieve_items(payload)

    items = r.get("results", [])
    confidence = r.get("confidence", "low")
    index_version = r.get("index_version")
    debug = r.get("debug", {})

    return {
        "items": items,
        "last_items": items,          # memory: raw search results
        "last_results": items[:5],    # memory: what user will see / choose from
        "confidence": confidence,
        "last_confidence": confidence,
        "index_version": index_version,
        "debug": {**state.get("debug", {}), **debug, "intent": state.get("intent"), "mode": "SEARCH"},
    }


def refine_node(state: AssistantState) -> Dict[str, Any]:
    items = list(state.get("last_items") or [])
    intent = state.get("intent")

    if intent == "REFINE_CHEAP":
        items = sorted(items, key=lambda x: float(x.get("price") or 1e18))
    elif intent == "REFINE_BEST":
        items = sorted(items, key=lambda x: float(x.get("score") or -1e18), reverse=True)

    shown = items[:5]
    return {
        "items": shown,
        "last_results": shown,
        "confidence": state.get("last_confidence", "low"),
    }


def compare_node(state: AssistantState) -> Dict[str, Any]:
    items = list(state.get("last_items") or [])
    nums = [int(n) for n in re.findall(r"\b\d+\b", state["user_message"])]

    selected: List[Dict[str, Any]] = []
    for n in nums:
        if 1 <= n <= len(items):
            selected.append(items[n - 1])

    return {
        "items": selected,
        "last_results": selected,
        "confidence": state.get("last_confidence", "low"),
    }


def addons_node(state: AssistantState) -> Dict[str, Any]:
    """
    Step 5C: retrieval-based add-ons.
    """
    import requests

    RETRIEVAL_URL = "http://localhost:8001/retrieve"

    last_items: List[dict] = state.get("last_items") or []
    if not last_items:
        return {
            "reply": "I don’t have any item context yet. Please search for something first.",
            "items": [],
            "confidence": "low",
        }

    anchor = last_items[0]
    anchor_name = anchor.get("item_name", "")
    city = anchor.get("city")
    veg_flag = anchor.get("veg_flag")
    anchor_item_id = anchor.get("item_id")

    similarity_query = f"veg sides or add-ons that go well with {anchor_name}"

    payload = {"query": similarity_query, "city": city, "veg_flag": veg_flag, "top_k": 15}

    try:
        resp = requests.post(RETRIEVAL_URL, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("results", [])
    except Exception:
        return {
            "reply": "I had trouble finding add-ons right now. Please try again.",
            "items": [],
            "confidence": "low",
        }

    add_ons = []
    for item in candidates:
        if item.get("item_id") == anchor_item_id:
            continue
        category = (item.get("category") or "").lower()
        if "burger" in category:
            continue
        add_ons.append(item)
        if len(add_ons) == 5:
            break

    if not add_ons:
        return {"reply": "I couldn’t find good add-ons for this item. Want to try a different dish?", "items": [], "confidence": "low"}

    return {
        "items": add_ons,
        "last_results": add_ons,   # crucial for cart selection after add-ons
        "confidence": state.get("last_confidence", "low") or "high",
    }


# ----------------------------
# CART NODES (Step 5D + 5E.x)
# ----------------------------
def add_to_cart_node(state: AssistantState) -> AssistantState:
    """
    Add item(s) to cart from last_results.

    Supports:
    - "add cheapest", "add cheapest x2"
    - "add best"
    - "add most expensive"
    - "add option 2"
    - "add option 1 and 3"
    - "add 2 of option 1 and 1 of option 4"
    - "option 3 x2"
    - "option 4 twice"

    Step 6A:
    - Case 1: last_results exists but user didn't specify what to add -> ask clarification (NO SEARCH, NO CART CHANGE)
    - Case 2: no last_results -> "search first"
    """
    last_results = state.get("last_results", []) or []
    msg = (state.get("user_message") or "").lower().strip()
    cart = state.get("cart", []) or []

    # -------------------------------
    # Step 6A Case 2: no last_results at all
    # -------------------------------
    if not last_results:
        state["reply"] = "I don’t have any recent results to add from. Please search first (e.g., 'veg burger under 200 in Bangalore')."
        state["items"] = []
        state["confidence"] = "low"
        return state

    # -------------------------------
    # Step 6A Case 1: ambiguous add (ask clarification)
    # Trigger if user says "add" but doesn't specify:
    # - shortcut (cheapest/best/most expensive)
    # - or option number (option + number)
    # - or multi-qty patterns (option 2 x3 / 2 of option 1)
    # -------------------------------
    wants_shortcut = any(k in msg for k in ["cheapest", "best", "most expensive", "costliest", "highest", "lowest"])
    has_option_word = "option" in msg
    has_any_number = bool(re.search(r"\b\d+\b", msg))

    has_qty_pattern = bool(
        re.search(r"\b(\d+)\s*of\s*option\s*(\d+)\b", msg) or
        re.search(r"\boption\s*(\d+)\s*(?:x|×|\*)\s*(\d+)\b", msg) or
        re.search(r"\boption\s*(\d+)\s*(twice|thrice)\b", msg)
    )

    # user is in ADD_TO_CART intent already; still keep guard here:
    if ("add" in msg) and (not wants_shortcut) and (not has_qty_pattern) and (not (has_option_word and has_any_number)):
        state["reply"] = (
            "Do you want to add from the last shown options?\n"
            "If yes, say **'add option 1'** (or 2/3/4/5) or **'add cheapest'** / **'add best'** / **'add most expensive'**."
        )
        state["items"] = cart
        state["confidence"] = "high"
        return state

    # -------------------------------
    # helpers
    # -------------------------------
    def _extract_qty_for_shortcut(text: str) -> int:
        text = (text or "").lower()

        m = re.search(r"\b(?:x|×|\*)\s*(\d+)\b", text)
        if m:
            return max(1, int(m.group(1)))

        if "twice" in text:
            return 2
        if "thrice" in text:
            return 3

        # allow "add best 3" ONLY if shortcut keyword exists
        m = re.search(r"\b(\d+)\b", text)
        if m and any(k in text for k in ["cheapest", "best", "most expensive", "costliest", "highest", "lowest"]):
            return max(1, int(m.group(1)))

        return 1

    selected_items: List[Tuple[Dict[str, Any], int]] = []

    # -------------------------------
    # Shortcut picks from last_results
    # -------------------------------
    if "cheapest" in msg or "lowest" in msg:
        item = _pick_cheapest(last_results)
        if item:
            selected_items.append((item, _extract_qty_for_shortcut(msg)))

    if not selected_items and "best" in msg:
        item = _pick_best(last_results)
        if item:
            selected_items.append((item, _extract_qty_for_shortcut(msg)))

    if not selected_items and ("most expensive" in msg or "costliest" in msg or "highest" in msg):
        item = _pick_most_expensive(last_results)
        if item:
            selected_items.append((item, _extract_qty_for_shortcut(msg)))

    # -------------------------------
    # Multi-qty patterns (strict "option" usage)
    # -------------------------------
    # Pattern A: "2 of option 1"
    for qty_str, opt_str in re.findall(r"(\d+)\s*of\s*option\s*(\d+)", msg):
        qty = int(qty_str)
        opt = int(opt_str)
        if 1 <= opt <= len(last_results) and qty >= 1:
            selected_items.append((last_results[opt - 1], qty))

    # Pattern B: "option 3 x2"
    for opt_str, qty_str in re.findall(r"option\s*(\d+)\s*(?:x|×|\*)\s*(\d+)", msg):
        opt = int(opt_str)
        qty = int(qty_str)
        if 1 <= opt <= len(last_results) and qty >= 1:
            selected_items.append((last_results[opt - 1], qty))

    # Pattern C: "option 4 twice/thrice"
    for opt_str, word in re.findall(r"option\s*(\d+)\s*(twice|thrice)", msg):
        opt = int(opt_str)
        qty = 2 if word == "twice" else 3
        if 1 <= opt <= len(last_results):
            selected_items.append((last_results[opt - 1], qty))

    # -------------------------------
    # Simple multi-option: "add option 1 and option 3"
    # -------------------------------
    if not selected_items:
        opts = re.findall(r"option\s*(\d+)", msg)
        for opt_str in opts:
            opt = int(opt_str)
            if 1 <= opt <= len(last_results):
                selected_items.append((last_results[opt - 1], 1))

    # -------------------------------
    # Invalid / nothing selected
    # -------------------------------
    if not selected_items:
        # user mentioned option/number but invalid
        if "option" in msg or re.search(r"\b\d+\b", msg):
            state["reply"] = f"Please choose valid option number(s) between 1 and {len(last_results)}."
            state["items"] = cart
            state["confidence"] = "low"
            return state

        # otherwise ambiguous
        state["reply"] = (
            "Do you want to add from the last shown options? "
            "If yes, say 'add option 1' or 'add cheapest'."
        )
        state["items"] = cart
        state["confidence"] = "high"
        return state

    # -------------------------------
    # Update cart
    # -------------------------------
    for item, qty in selected_items:
        existing = next((c for c in cart if c.get("item_id") == item.get("item_id")), None)
        if existing:
            existing["qty"] = int(existing.get("qty", 1)) + qty
        else:
            cart.append({
                "item_id": item.get("item_id"),
                "item_name": item.get("item_name"),
                "price": item.get("price"),
                "veg_flag": item.get("veg_flag"),
                "city": item.get("city"),
                "restaurant_id": item.get("restaurant_id"),
                "qty": qty,
            })

    total = _cart_total(cart)
    added_lines = [f"- {it['item_name']} × {q}" for it, q in selected_items]

    state["cart"] = cart
    state["items"] = cart
    state["confidence"] = "high"
    state["reply"] = (
        "✅ Added to cart:\n"
        + "\n".join(added_lines)
        + f"\n🛒 Cart items: {len(cart)} | Total: ₹{round(total, 2)}"
    )
    return state


def show_cart_node(state: AssistantState) -> Dict[str, Any]:
    cart = list(state.get("cart") or [])
    if not cart:
        return {"reply": "🛒 Your cart is empty.", "items": [], "confidence": "low"}

    lines = ["🛒 Your cart:"]
    for i, c in enumerate(cart, start=1):
        lines.append(f"{i}) {c['item_name']} × {c.get('qty', 1)} — ₹{c['price']} ({c['veg_flag']})")

    total = _cart_total(cart)
    lines.append(f"\nTotal: ₹{round(total, 2)}")
    return {"reply": "\n".join(lines), "items": cart, "confidence": "high"}


def remove_from_cart_node(state: AssistantState) -> Dict[str, Any]:
    cart = list(state.get("cart") or [])
    if not cart:
        return {"reply": "Your cart is already empty.", "items": [], "confidence": "low"}

    opts = _parse_option_numbers(state["user_message"])
    if not opts:
        return {"reply": "Tell me which cart option to remove (e.g., 'remove 1').", "items": cart, "confidence": "low"}

    opt = opts[0]
    if not (1 <= opt <= len(cart)):
        return {"reply": f"Please choose a valid cart option (1 to {len(cart)}).", "items": cart, "confidence": "low"}

    removed = cart.pop(opt - 1)
    total = _cart_total(cart)

    reply = f"🗑️ Removed: {removed.get('item_name')}\n🛒 Cart items: {len(cart)} | Total: ₹{round(total, 2)}"
    return {"reply": reply, "cart": cart, "items": cart, "confidence": "high"}


def clear_cart_node(state: AssistantState) -> Dict[str, Any]:
    return {"reply": "🧹 Cart cleared.", "cart": [], "items": [], "confidence": "high"}


def update_cart_qty_node(state: AssistantState) -> Dict[str, Any]:
    cart = list(state.get("cart") or [])

    if not cart:
        return {
            "reply": "🛒 Your cart is empty.",
            "items": [],
            "confidence": "low"
        }

    msg = (state.get("user_message") or "").lower()

    import re
    nums = re.findall(r"\b\d+\b", msg)

    if len(nums) < 2:
        return {
            "reply": "Please specify cart item number and quantity (e.g., 'set 1 to 3').",
            "items": cart,
            "confidence": "low"
        }

    index = int(nums[0])
    qty = int(nums[1])

    if not (1 <= index <= len(cart)):
        return {
            "reply": f"Choose a valid cart item (1 to {len(cart)}).",
            "items": cart,
            "confidence": "low"
        }

    item = cart[index - 1]

    if qty <= 0:
        removed = cart.pop(index - 1)
        total = sum(c["price"] * c["qty"] for c in cart)
        return {
            "reply": f"🗑️ Removed: {removed['item_name']} (qty set to 0)\n🛒 Cart items: {len(cart)} | Total: ₹{round(total,2)}",
            "cart": cart,
            "items": cart,
            "confidence": "high"
        }

    item["qty"] = qty
    total = sum(c["price"] * c["qty"] for c in cart)

    return {
        "reply": f"✅ Updated: {item['item_name']} qty = {qty}\n🛒 Cart items: {len(cart)} | Total: ₹{round(total,2)}",
        "cart": cart,
        "items": cart,
        "confidence": "high"
    }


def response_node(state: AssistantState) -> Dict[str, Any]:
    """
    Final formatting step.
    If state already has reply (guard/cart nodes), keep it.
    Else format using generate_response.
    """
    if state.get("halt") and state.get("reply"):
        return {
            "reply": state["reply"],
            "items": state.get("items", []),
            "confidence": state.get("confidence", "low"),
            "last_items": state.get("last_items", []),
            "last_results": state.get("last_results", []),
            "cart": state.get("cart", []),
        }

    if state.get("reply"):
        return {
            "reply": state["reply"],
            "items": state.get("items", []),
            "confidence": state.get("confidence", "high"),
            "last_items": state.get("last_items", []),
            "last_results": state.get("last_results", []),
            "cart": state.get("cart", []),
        }

    items = state.get("items", [])
    confidence = state.get("confidence", "low")
    reply = generate_response("", "", items, confidence)

    shown = items[:5]
    return {
        "reply": reply,
        "items": shown,
        "confidence": confidence,
        "last_items": state.get("last_items", []),
        "last_results": shown,
        "cart": state.get("cart", []),
    }


'''
We update add_to_cart_node so it can:
1. add cheapest item from last_results
2. add best item (highest score) from last_results
3. add most expensive item from last_results
4. still support “add option 2”
5. still default to option 1 if nothing is specified
'''