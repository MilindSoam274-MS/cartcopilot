import time
from .observability import (
    ASSISTANT_LLM_CALLS_TOTAL,
    ASSISTANT_LLM_LATENCY,
)

def generate_response(system_prompt: str, user_prompt: str, items: list, confidence: str) -> str:
    start = time.perf_counter()
    try:
        if not items:
            msg = "I couldn’t find a good match. Which city and budget should I use, and do you want Veg or Non-veg?"
            ASSISTANT_LLM_CALLS_TOTAL.labels(status="success").inc()
            return msg

        lines = []
        for i, it in enumerate(items[:5], start=1):
            price = it.get("price")
            veg = it.get("veg_flag")
            name = it.get("item_name")
            lines.append(f"{i}) {name} — ₹{price} ({veg})")

        msg = "Here are the best matches:\n" + "\n".join(lines)

        if confidence == "low":
            msg += "\n\nIf you tell me your exact budget and whether you want spicy/cheesy, I can narrow it down."
        else:
            msg += "\n\nWant me to recommend the best value option or the tastiest one?"

        ASSISTANT_LLM_CALLS_TOTAL.labels(status="success").inc()
        return msg
    except Exception:
        ASSISTANT_LLM_CALLS_TOTAL.labels(status="error").inc()
        raise
    finally:
        ASSISTANT_LLM_LATENCY.observe(time.perf_counter() - start)