import pytest
from ingestion.handler import validate_and_build_event


def test_valid_order_creation():
    body = {
        "event_type": "ORDER_CREATED",
        "payload": {
            "order_id": "ORD-1001",
            "product": "Wireless Headphones",
            "quantity": 1,
            "total": 1999.00,
        },
    }
    result = validate_and_build_event(body)

    assert result["event_type"] == "ORDER_CREATED"
    assert result["payload"]["order_id"] == "ORD-1001"
    assert result["payload"]["product"] == "Wireless Headphones"
    assert result["payload"]["quantity"] == 1
    assert result["event_id"] is not None
    assert result["timestamp"] is not None


def test_missing_payload():
    body = {"event_type": "ORDER_CREATED"}
    with pytest.raises(ValueError, match="Missing or invalid 'payload'"):
        validate_and_build_event(body)


def test_invalid_event_type():
    body = {
        "event_type": "USER_SIGNUP",
        "payload": {
            "order_id": "ORD-1001",
            "product": "Headphones",
            "quantity": 1,
            "total": 1999,
        },
    }
    with pytest.raises(ValueError, match="Expected 'ORDER_CREATED'"):
        validate_and_build_event(body)


def test_invalid_quantity():
    body = {
        "event_type": "ORDER_CREATED",
        "payload": {
            "order_id": "ORD-1001",
            "product": "Headphones",
            "quantity": 0,
            "total": 1999,
        },
    }
    with pytest.raises(ValueError, match="positive integer"):
        validate_and_build_event(body)