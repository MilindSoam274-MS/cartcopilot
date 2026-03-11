from prometheus_client import Counter, Histogram

# =========================
# Assistant Business Metrics
# =========================

CHAT_TURNS_TOTAL = Counter(
    "assistant_chat_turns_total",
    "Total chat turns received by assistant-service",
)

INTENTS_TOTAL = Counter(
    "assistant_intents_total",
    "Total detected intents",
    ["intent"],
)

GUARD_HALTS_TOTAL = Counter(
    "assistant_guard_halts_total",
    "Total guard halts (flow stopped due to missing context)",
    ["reason"],  # NO_LAST_RESULTS, NO_LAST_ITEMS
)

RETRIEVAL_REQUESTS_TOTAL = Counter(
    "assistant_retrieval_requests_total",
    "Total retrieval-service calls from assistant-service",
    ["status"],  # ok, error
)

RETRIEVAL_LATENCY_SECONDS = Histogram(
    "assistant_retrieval_latency_seconds",
    "Latency for retrieval-service calls in seconds",
)

SEARCHES_TOTAL = Counter(
    "assistant_searches_total",
    "Total searches completed",
    ["confidence"],  # low/high/medium if ever
)

CART_ACTIONS_TOTAL = Counter(
    "assistant_cart_actions_total",
    "Total cart actions performed",
    ["action"],  # add, remove, clear, show, update_qty
)

GRAPH_LATENCY_SECONDS = Histogram(
    "assistant_graph_latency_seconds",
    "End-to-end LangGraph invoke latency in seconds",
)