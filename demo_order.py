import sys
import time
import requests

# Default placeholder - replace with actual API Gateway URL once Member 3 deploys
DEFAULT_API_URL = "http://localhost:8000"


def place_order(
    api_url: str,
    order_id: str,
    product: str,
    quantity: int,
    total: float,
    webhook_url: str = None,
):
    payload = {
        "event_type": "ORDER_CREATED",
        "payload": {
            "order_id": order_id,
            "product": product,
            "quantity": quantity,
            "total": total,
        },
    }
    if webhook_url:
        payload["destination_url"] = webhook_url

    print(
        f"\n🛒 [Shopping App] Customer placing order: {quantity}x '{product}' (${total:.2f})..."
    )
    try:
        response = requests.post(f"{api_url}/events", json=payload, timeout=5)
    except Exception as exc:
        print(f"❌ Connection error: {exc}")
        return None

    print(f"<- API Response ({response.status_code}):", response.json())

    if response.status_code != 202:
        print("❌ Order ingestion failed.")
        return None

    return response.json().get("event_id")


def track_order(api_url: str, event_id: str, max_polls: int = 6):
    print(
        f"\n🔍 [Order Tracker] Polling GET /events/{event_id} to track delivery status..."
    )
    for i in range(max_polls):
        time.sleep(2)
        try:
            res = requests.get(f"{api_url}/events/{event_id}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                status = data.get("status")
                attempts = data.get("attempts", 0)
                print(
                    f"   [Poll {i+1}] Status: {status} | Delivery Attempts: {attempts}"
                )
                if status in ["SUCCESS", "FAILED"]:
                    print(f"✅ Final State Reached: {status}")
                    break
            else:
                print(f"   [Poll {i+1}] Status lookup returned {res.status_code}")
        except Exception as exc:
            print(f"   [Poll {i+1}] Check failed: {exc}")


if __name__ == "__main__":
    api_url = (
        sys.argv[1].rstrip("/") if len(sys.argv) > 1 else DEFAULT_API_URL
    )
    print(f"Connecting to Webhook API at: {api_url}")

    # Simulate placing an order for Headphones
    event_id = place_order(
        api_url=api_url,
        order_id="ORD-1001",
        product="Sony WH-1000XM5 Headphones",
        quantity=1,
        total=399.99,
    )

    if event_id:
        track_order(api_url, event_id)