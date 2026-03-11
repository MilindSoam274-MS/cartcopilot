import json
import os
import redis


def _redis():
    return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def test_show_cart_writes_session_to_redis(client):
    session_id = "test_show_cart_1"
    r = _redis()
    r.delete(session_id)

    resp = client.post("/chat", json={"session_id": session_id, "message": "show cart"})
    assert resp.status_code == 200
    data = resp.json()

    # Minimal response contract checks
    assert "reply" in data
    assert "confidence" in data
    assert "items" in data
    assert isinstance(data["items"], list)

    # Redis persistence check
    raw = r.get(session_id)
    assert raw is not None, "Expected assistant-service to persist session state in Redis"

    state = json.loads(raw)
    assert state.get("session_id") == session_id
    assert "intent" in state