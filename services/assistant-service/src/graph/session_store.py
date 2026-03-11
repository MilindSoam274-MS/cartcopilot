import json
from typing import Any, Dict

import redis


# ✅ Local Redis default
# If you later dockerize, you can change host="redis"
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

TTL_SECONDS = 60 * 60 * 6  # 6 hours


def get_state(session_id: str) -> Dict[str, Any]:
    raw = r.get(session_id)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    # store full state (safe + simple)
    r.set(session_id, json.dumps(state), ex=TTL_SECONDS)
