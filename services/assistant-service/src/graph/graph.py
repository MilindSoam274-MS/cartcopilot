from langgraph.graph import StateGraph, END
from .schema import AssistantState
from .nodes import (
    intent_node,
    guard_node,
    search_node,
    refine_node,
    compare_node,
    addons_node,
    add_to_cart_node,
    show_cart_node,
    remove_from_cart_node,
    clear_cart_node,
    update_cart_qty_node,
    response_node,
)


def route_after_intent(state: AssistantState) -> str:
    intent = state.get("intent")

    if intent == "SEARCH":
        return "search_node"

    if intent in ("REFINE_CHEAP", "REFINE_BEST", "COMPARE", "ADD_ONS", "ADD_TO_CART", "REMOVE_FROM_CART"):
        return "guard_node"

    if intent == "SHOW_CART":
        return "show_cart_node"

    if intent == "CLEAR_CART":
        return "clear_cart_node"

    if intent == "UPDATE_CART_QTY":
        return "update_cart_qty_node"

    return "search_node"


def route_after_guard(state: AssistantState) -> str:
    if state.get("halt"):
        return "response_node"

    intent = state.get("intent")

    if intent in ("REFINE_CHEAP", "REFINE_BEST"):
        return "refine_node"
    if intent == "COMPARE":
        return "compare_node"
    if intent == "ADD_ONS":
        return "addons_node"
    if intent == "ADD_TO_CART":
        return "add_to_cart_node"
    if intent == "REMOVE_FROM_CART":
        return "remove_from_cart_node"
    if intent == "UPDATE_CART_QTY":
        return "update_cart_qty_node"

    return "response_node"


def build_graph():
    g = StateGraph(AssistantState)

    g.add_node("intent_node", intent_node)
    g.add_node("guard_node", guard_node)

    g.add_node("search_node", search_node)
    g.add_node("refine_node", refine_node)
    g.add_node("compare_node", compare_node)
    g.add_node("addons_node", addons_node)

    g.add_node("add_to_cart_node", add_to_cart_node)
    g.add_node("show_cart_node", show_cart_node)
    g.add_node("remove_from_cart_node", remove_from_cart_node)
    g.add_node("clear_cart_node", clear_cart_node)
    g.add_node("update_cart_qty_node", update_cart_qty_node)

    g.add_node("response_node", response_node)

    g.set_entry_point("intent_node")

    g.add_conditional_edges("intent_node", route_after_intent)

    g.add_edge("search_node", "response_node")
    g.add_edge("refine_node", "response_node")
    g.add_edge("compare_node", "response_node")
    g.add_edge("addons_node", "response_node")

    g.add_edge("add_to_cart_node", "response_node")
    g.add_edge("show_cart_node", "response_node")
    g.add_edge("remove_from_cart_node", "response_node")
    g.add_edge("clear_cart_node", "response_node")
    g.add_edge("update_cart_qty_node", "response_node")

    g.add_conditional_edges("guard_node", route_after_guard)

    g.add_edge("response_node", END)

    return g.compile()


GRAPH = build_graph()