'''
📌 Why rules first?

1. Predictable
2. Debuggable
3. Perfect for Phase-1
4. Agents come later
'''

# src/intent.py
import re

'''
def detect_intent(text: str) -> str:
    """
    Very simple rule-based intent detection for Phase 1.

    Order matters (more specific first).
    """
    msg = (text or "").lower().strip()

    # Cart display / clear
    if any(k in msg for k in ["show cart", "view cart", "my cart", "cart?"]):
        return "SHOW_CART"
    if "clear cart" in msg or "empty cart" in msg:
        return "CLEAR_CART"

    # Cart quantity edit (Step 5E.5)
    # Must contain explicit cart/qty language to avoid budget-number accidents.
    if (
        ("cart" in msg or "qty" in msg or "quantity" in msg)
        and any(k in msg for k in ["set", "change", "update", "increase", "decrease", "reduce", "make"])
    ):
        return "UPDATE_CART_QTY"

    # Add to cart
    if any(k in msg for k in ["add to cart", "add cart", "add option", "add cheapest", "add best", "add expensive"]):
        return "ADD_TO_CART"

    # Remove from cart
    if any(k in msg for k in ["remove", "delete"]) and "cart" in msg:
        return "REMOVE_FROM_CART"
    # also allow "remove 1" after user is in cart context
    if msg.startswith("remove ") or msg.startswith("delete "):
        return "REMOVE_FROM_CART"

    # Follow-ups
    if any(k in msg for k in ["cheaper", "cheap", "lowest", "under budget"]):
        return "REFINE_CHEAP"
    if any(k in msg for k in ["best", "top", "highest"]):
        return "REFINE_BEST"
    if "compare" in msg:
        return "COMPARE"
    if any(k in msg for k in ["add-ons", "addons", "side", "sides", "similar"]):
        return "ADD_ONS"

    # Default
    return "SEARCH"
'''

import re

def detect_intent(text: str) -> str:
    t = (text or "").strip().lower()

    # ----------------------------
    # CART SHOW / CLEAR
    # ----------------------------
    if re.search(r"\b(show|view|see)\s+(cart|basket)\b|\bmy\s+cart\b", t):
        return "SHOW_CART"

    if re.search(r"\b(clear|empty)\s+(cart|basket)\b", t):
        return "CLEAR_CART"

    # ----------------------------
    # CART REMOVE
    # ----------------------------
    if re.search(r"\b(remove|delete)\b", t) and re.search(r"\b\d+\b", t):
        return "REMOVE_FROM_CART"

    # ----------------------------
    # CART QTY UPDATE (THIS FIXES YOUR TEST 7)
    # examples: "set 1 to 3", "qty 2 = 5", "increase 1", "decrease 1", "set quantity 1 to 2"
    # ----------------------------
    has_cart_index = bool(re.search(r"\b\d+\b", t))   # cart index like 1,2,3
    has_qty_words = bool(re.search(r"\b(qty|quantity|set|update|increase|decrease)\b", t))
    has_two_numbers = len(re.findall(r"\b\d+\b", t)) >= 2

    # set/update patterns
    if has_qty_words and has_cart_index and (has_two_numbers or re.search(r"\b(increase|decrease)\b", t)):
        return "UPDATE_CART_QTY"

    # ----------------------------
    # ADD TO CART
    # supports:
    # - "add option 1"
    # - "add cheapest", "add best", "add most expensive"
    # - "add 2 of option 1 and 1 of option 3"
    # - "option 2 x3"
    # - "add item" (Step 6A will handle clarification in nodes, but intent should still be ADD_TO_CART)
    # ----------------------------
    if re.search(r"\badd\b", t):
        # "add most expensive / costliest / highest price"
        if re.search(r"\b(most\s+expensive|costliest|highest\s+price|max\s+price)\b", t):
            return "ADD_TO_CART"
        if re.search(r"\b(cheapest|best|option)\b", t):
            return "ADD_TO_CART"
        # still treat plain "add" as add-to-cart (Step 6A will ask clarification)
        return "ADD_TO_CART"

    # ----------------------------
    # ADD-ONS / COMPARE / REFINE
    # ----------------------------
    if re.search(r"\b(add[\s-]?ons?|sides?)\b", t):
        return "ADD_ONS"

    if re.search(r"\bcompare\b", t):
        return "COMPARE"

    if re.search(r"\b(cheapest|low(est)?\s+price)\b", t) and not re.search(r"\badd\b", t):
        return "REFINE_CHEAP"

    if re.search(r"\b(best|top|highest\s+score)\b", t) and not re.search(r"\badd\b", t):
        return "REFINE_BEST"

    # ✅ Step 6: ambiguous add should still be ADD_TO_CART (not SEARCH)
    if any(k in t for k in ["add to cart", "add item", "add this", "add it"]) or t == "add" or t.startswith("add "):
        return "ADD_TO_CART"
    # ----------------------------
    # DEFAULT = SEARCH
    # ----------------------------
    return "SEARCH"