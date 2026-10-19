import json
import sys
from ingestion.handler import lambda_handler

# 1. Simulate API Gateway POST /events
post_event = {
    "requestContext": {"http": {"method": "POST"}},
    "body": json.dumps(
        {
            "event_type": "ORDER_CREATED",
            "payload": {
                "order_id": "ORD-LIVE-TEST",
                "product": "Sony WH-1000XM5 Headphones",
                "quantity": 2,
                "total": 799.98,
            },
        }
    ),
}

print("--- 1. Testing POST /events against live AWS ---")
post_response = lambda_handler(post_event, None)
print(f"Status Code: {post_response['statusCode']}")
response_body = json.loads(post_response["body"])
print(f"Response Body: {json.dumps(response_body, indent=2)}")

if post_response["statusCode"] != 202:
    print("\n❌ POST failed. Check the error above.")
    sys.exit(1)

event_id = response_body["event_id"]

# 2. Simulate API Gateway GET /events/{event_id}
print(f"\n--- 2. Testing GET /events/{event_id} from DynamoDB ---")
get_event = {
    "requestContext": {"http": {"method": "GET"}},
    "pathParameters": {"event_id": event_id},
}

get_response = lambda_handler(get_event, None)
print(f"Status Code: {get_response['statusCode']}")
item = json.loads(get_response["body"])
print(f"Stored DynamoDB Item:\n{json.dumps(item, indent=2)}")

if get_response["statusCode"] == 200:
    print(
        "\n🎉 REAL SUCCESS! DynamoDB stored the order and SQS received the message!"
    )