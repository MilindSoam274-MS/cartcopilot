import os
import json
from typing import Any, Dict

import redis

# -------------------------------------------------
# Redis Configuration
# -------------------------------------------------

# If running via Docker compose:
# use "redis" as host inside container
# If running service locally:
# use localhost

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TTL_SECONDS = 60 * 60 * 24*7  # 24*7 hours

# decode_responses=True => strings instead of bytes
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_state(session_id: str) -> Dict[str, Any]:
    """
    Hardening (Step 7C):
    - If Redis is down, DO NOT crash FastAPI.
    - Return empty state => behaves like a new session.
    """
    try:
        raw = r.get(session_id)
        if not raw:
            return {}
        return json.loads(raw)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        # Redis is down -> graceful fallback
        return {}
    except Exception:
        # Bad JSON or unexpected -> safe fallback
        return {}


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    """
    Hardening (Step 7C):
    - If Redis is down, DO NOT crash.
    - Just skip saving (session memory won't persist until Redis is back).
    """
    try:
        r.set(session_id, json.dumps(state), ex=TTL_SECONDS)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        return
    except Exception:
        return


def clear_state(session_id: str) -> None:
    try:
        r.delete(session_id)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        return
    except Exception:
        return