import json

def seed_cart(redis_client, session_id: str):
    payload = {
        "session_id": session_id,
        "cart": [
            {
                "item_id": "item_1",
                "item_name": "Test Burger",
                "price": 100.0,
                "qty": 1,
                "restaurant_id": 123,
                "city": "Bangalore",
                "veg_flag": "Veg",
            }
        ],
    }
    redis_client.set(session_id, json.dumps(payload))


def test_address_before_start_fails(client, session_id):
    resp = client.post("/checkout/address", json={
        "session_id": session_id,
        "address": {
            "name": "Milind",
            "phone": "9999999999",
            "line1": "SG Palya",
            "line2": "Near XYZ",
            "city": "Bangalore",
            "pincode": "560029",
            "landmark": "Near bus stop"
        }
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert data["error_code"] == "CHECKOUT_NOT_STARTED"


def test_payment_before_address_fails(client, redis_client, session_id):
    seed_cart(redis_client, session_id)

    # start checkout -> should go to AWAITING_ADDRESS
    r1 = client.post("/checkout/start", json={"session_id": session_id}).json()
    assert r1["status"] == "ok"
    assert r1["checkout_state"] == "AWAITING_ADDRESS"

    # try payment directly
    resp = client.post("/checkout/payment", json={"session_id": session_id, "payment_method": "COD"})
    data = resp.json()
    assert data["status"] == "error"
    assert data["error_code"] in ("INVALID_STATE", "ADDRESS_REQUIRED", "CHECKOUT_NOT_IN_EXPECTED_STATE")


def test_confirm_false_cancels_and_no_order_created(client, redis_client, session_id):
    seed_cart(redis_client, session_id)

    # start
    r1 = client.post("/checkout/start", json={"session_id": session_id}).json()
    assert r1["status"] == "ok"

    # address
    r2 = client.post("/checkout/address", json={
        "session_id": session_id,
        "address": {
            "name": "Milind",
            "phone": "9999999999",
            "line1": "SG Palya",
            "line2": None,
            "city": "Bangalore",
            "pincode": "560029",
            "landmark": None
        }
    }).json()
    assert r2["status"] == "ok"
    assert r2["checkout_state"] == "AWAITING_PAYMENT"

    # payment
    r3 = client.post("/checkout/payment", json={"session_id": session_id, "payment_method": "COD"}).json()
    assert r3["status"] == "ok"
    assert r3["checkout_state"] == "CONFIRMING"

    # confirm false -> CANCELLED
    r4 = client.post("/checkout/confirm", json={"session_id": session_id, "confirm": False}).json()
    assert r4["status"] == "ok"
    assert r4["checkout_state"] == "CANCELLED"

    # no last order pointer
    last_order = redis_client.get(f"session:{session_id}:last_order_id")
    assert last_order is None


def test_idempotent_confirm_true_returns_same_order_id(client, redis_client, session_id):
    seed_cart(redis_client, session_id)

    client.post("/checkout/start", json={"session_id": session_id})
    client.post("/checkout/address", json={
        "session_id": session_id,
        "address": {
            "name": "Milind",
            "phone": "9999999999",
            "line1": "SG Palya",
            "line2": "Near XYZ",
            "city": "Bangalore",
            "pincode": "560029",
            "landmark": "Near bus stop"
        }
    })
    client.post("/checkout/payment", json={"session_id": session_id, "payment_method": "COD"})

    r1 = client.post("/checkout/confirm", json={"session_id": session_id, "confirm": True}).json()
    assert r1["status"] == "ok"
    assert r1["checkout_state"] == "PLACED"
    order_id_1 = r1["order_id"]
    assert order_id_1

    # confirm again
    r2 = client.post("/checkout/confirm", json={"session_id": session_id, "confirm": True}).json()
    assert r2["status"] == "ok"
    assert r2["checkout_state"] == "PLACED"
    assert r2["order_id"] == order_id_1

    # ensure order exists in Redis
    raw = redis_client.get(f"order:{order_id_1}")
    assert raw is not None