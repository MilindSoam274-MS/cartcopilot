from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import Optional

from .graph.graph import GRAPH
from .graph.redis_store import get_state, save_state

from .observability import (
    setup_observability,
    ASSISTANT_MESSAGES_TOTAL,
    ASSISTANT_LOW_CONFIDENCE_TOTAL,
    ASSISTANT_FALLBACK_TOTAL,
    ASSISTANT_CART_ADD_TOTAL,
    ASSISTANT_CART_REMOVE_TOTAL,
    ASSISTANT_SHOW_CART_TOTAL,
    ASSISTANT_CLEAR_CART_TOTAL,
    ASSISTANT_UPDATE_CART_QTY_TOTAL,
)

app = FastAPI(title="assistant-service")
setup_observability(app)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    city: Optional[str] = None
    veg_flag: Optional[str] = None
    max_price: Optional[float] = None


@app.post("/chat")
def chat(req: ChatRequest):
    # -----------------------------------------
    # 1️⃣ Load session memory from Redis
    # -----------------------------------------
    mem = get_state(req.session_id)

    # -----------------------------------------
    # 2️⃣ Build graph state
    # -----------------------------------------
    state = {
        "session_id": req.session_id,
        "user_message": req.message,

        # user constraints
        "city": req.city or mem.get("city"),
        "veg_flag": req.veg_flag or mem.get("veg_flag"),
        "max_price": req.max_price if req.max_price is not None else mem.get("max_price"),

        # memory
        "last_items": mem.get("last_items", []),
        "last_results": mem.get("last_results", []),
        "last_confidence": mem.get("last_confidence"),
        "cart": mem.get("cart", []),

        # defaults
        "items": [],
        "confidence": "low",
        "debug": {},
        "reply": "",
        "halt": False,
    }

    # -----------------------------------------
    # 3️⃣ Run graph
    # -----------------------------------------
    out = GRAPH.invoke(state)

    # -----------------------------------------
    # 4️⃣ Persist full state to Redis
    # -----------------------------------------
    save_state(req.session_id, out)

    # -----------------------------------------
    # 5️⃣ Business Metrics
    # -----------------------------------------
    intent = out.get("intent", "UNKNOWN")
    confidence = out.get("confidence", "low")
    reply = (out.get("reply") or "").lower()

    ASSISTANT_MESSAGES_TOTAL.labels(intent=intent).inc()

    if confidence == "low":
        ASSISTANT_LOW_CONFIDENCE_TOTAL.inc()

    # fallback / clarification heuristics
    if "please search first" in reply or "which city and budget" in reply or "i don’t have any recent results" in reply:
        ASSISTANT_FALLBACK_TOTAL.inc()

    if intent == "ADD_TO_CART":
        ASSISTANT_CART_ADD_TOTAL.inc()
    elif intent == "REMOVE_FROM_CART":
        ASSISTANT_CART_REMOVE_TOTAL.inc()
    elif intent == "SHOW_CART":
        ASSISTANT_SHOW_CART_TOTAL.inc()
    elif intent == "CLEAR_CART":
        ASSISTANT_CLEAR_CART_TOTAL.inc()
    elif intent == "UPDATE_CART_QTY":
        ASSISTANT_UPDATE_CART_QTY_TOTAL.inc()

    # -----------------------------------------
    # 6️⃣ Return response
    # -----------------------------------------
    return {
        "reply": out.get("reply", ""),
        "items": out.get("items", []),
        "confidence": out.get("confidence", "low"),
    }