import json
import os
import redis


def _redis():
    return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def test_search_add_show_remove_flow(client):
    session_id = "test_add_remove_1"
    r = _redis()
    r.delete(session_id)

    # 1) SEARCH
    resp1 = client.post("/chat", json={"session_id": session_id, "message": "veg burger bangalore"})
    assert resp1.status_code == 200
    j1 = resp1.json()
    assert "items" in j1 and isinstance(j1["items"], list)

    # 2) ADD option 1
    resp2 = client.post("/chat", json={"session_id": session_id, "message": "add option 1"})
    assert resp2.status_code == 200
    j2 = resp2.json()
    assert "reply" in j2

    # Redis should now have cart
    raw2 = r.get(session_id)
    assert raw2 is not None
    state2 = json.loads(raw2)
    assert "cart" in state2
    assert isinstance(state2["cart"], list)
    assert len(state2["cart"]) >= 1

    # 3) SHOW CART
    resp3 = client.post("/chat", json={"session_id": session_id, "message": "show cart"})
    assert resp3.status_code == 200
    j3 = resp3.json()
    assert "reply" in j3

    # 4) REMOVE option 1 (you said remove option 1 works)
    resp4 = client.post("/chat", json={"session_id": session_id, "message": "remove option 1"})
    assert resp4.status_code == 200
    j4 = resp4.json()
    assert "reply" in j4

    # Ensure session still exists and cart is valid list (may be empty after remove)
    state4 = json.loads(r.get(session_id))
    assert "cart" in state4
    assert isinstance(state4["cart"], list)