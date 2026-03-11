import os
import json
import uuid
import pytest
import redis
from fastapi.testclient import TestClient

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Import app from your checkout-service main.py
from src.main import app



@pytest.fixture(scope="session")
def redis_client():
    """
    Uses the same REDIS_URL your service uses.
    Default aligns with docker-compose service name 'redis'.
    Override when needed:
      set REDIS_URL=redis://localhost:6379/0
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    # quick ping
    r.ping()
    return r


@pytest.fixture()
def session_id():
    return f"test_{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def client():
    return TestClient(app)


def _delete_keys_for_session(r, session_id: str):
    # Adjust patterns based on your keys.
    patterns = [
        f"{session_id}",                 # assistant session key in redis (cart/state)
        f"checkout:{session_id}",        # checkout object
        f"session:{session_id}:last_order_id",
    ]
    for p in patterns:
        r.delete(p)


@pytest.fixture(autouse=True)
def cleanup_redis(redis_client, session_id):
    # runs before test
    _delete_keys_for_session(redis_client, session_id)
    yield
    # runs after test
    _delete_keys_for_session(redis_client, session_id)