import json

def seed_cart(redis_client, session_id: str):
    # minimal session payload checkout expects
    payload = {
        "session_id": session_id,
        "cart": [
            {
                "item_id": "item_1",
                "item_name": "Test Burger",
                "price": 100.0,
                "qty": 2,
                "restaurant_id": 123,
                "city": "Bangalore",
                "veg_flag": "Veg",
            }
        ],
    }
    redis_client.set(session_id, json.dumps(payload))
    return payload


def test_checkout_start_creates_checkout_key(client, redis_client, session_id):
    seed_cart(redis_client, session_id)

    resp = client.post("/checkout/start", json={"session_id": session_id})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["checkout_state"] == "AWAITING_ADDRESS"

    # Verify checkout object stored in Redis
    raw = redis_client.get(f"checkout:{session_id}")
    assert raw is not None, "checkout key not created in Redis"