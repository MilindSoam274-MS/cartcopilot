import time
import requests
from .config import RETRIEVAL_BASE_URL
from .observability import (
    ASSISTANT_RETRIEVAL_CALLS_TOTAL,
    ASSISTANT_RETRIEVAL_LATENCY,
)

def retrieve_items(payload: dict) -> dict:
    start = time.perf_counter()
    try:
        resp = requests.post(
            f"{RETRIEVAL_BASE_URL}/retrieve",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        ASSISTANT_RETRIEVAL_CALLS_TOTAL.labels(status="success").inc()
        return resp.json()
    except Exception:
        ASSISTANT_RETRIEVAL_CALLS_TOTAL.labels(status="error").inc()
        raise
    finally:
        ASSISTANT_RETRIEVAL_LATENCY.observe(time.perf_counter() - start)