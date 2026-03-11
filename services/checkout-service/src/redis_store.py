import json
from typing import Any, Dict, Optional

import redis
from redis.exceptions import ConnectionError, TimeoutError

from .config import REDIS_URL, CHECKOUT_TTL_SECONDS, ORDER_TTL_SECONDS

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def _safe_json_load(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}

def get_json(key: str) -> Dict[str, Any]:
    try:
        raw = r.get(key)
        return _safe_json_load(raw)
    except (ConnectionError, TimeoutError):
        return {}
    except Exception:
        return {}

def set_json(key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
    try:
        ok = r.set(key, json.dumps(value), ex=ttl_seconds if ttl_seconds > 0 else None)
        print(f"[redis] SET key={key} ttl={ttl_seconds} ok={ok}")
    #except (ConnectionError, TimeoutError):
    #    return
    except Exception as e:
        print(f"[redis] SET failed key={key} err={e}")
        return

def set_text(key: str, value: str, ttl_seconds: int) -> None:
    try:
        r.set(key, value, ex=ttl_seconds if ttl_seconds > 0 else None)
    except (ConnectionError, TimeoutError):
        return
    except Exception:
        return


# --- Step 8 key helpers ---
def session_key(session_id: str) -> str:
    return session_id

def checkout_key(session_id: str) -> str:
    return f"checkout:{session_id}"

def order_key(order_id: str) -> str:
    return f"order:{order_id}"

def last_order_key(session_id: str) -> str:
    return f"session:{session_id}:last_order_id"


# --- TTL helpers (explicit) ---
def save_checkout(session_id: str, payload: Dict[str, Any]) -> None:
    set_json(checkout_key(session_id), payload, CHECKOUT_TTL_SECONDS)

def load_checkout(session_id: str) -> Dict[str, Any]:
    return get_json(checkout_key(session_id))

def save_order(order_id: str, payload: Dict[str, Any]) -> None:
    set_json(order_key(order_id), payload, ORDER_TTL_SECONDS)

def save_last_order(session_id: str, order_id: str) -> None:
    # keep it same as order ttl
    set_text(last_order_key(session_id), order_id, ORDER_TTL_SECONDS)

def load_last_order_id(session_id: str) -> str:
    try:
        raw = r.get(last_order_key(session_id))
        return raw or ""
    except Exception:
        return ""