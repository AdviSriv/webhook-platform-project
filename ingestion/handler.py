import json
import os
import uuid
from datetime import datetime, timezone
import boto3

# Configuration via environment variables (Member 3 will set these in AWS)
TABLE_NAME = os.environ.get("EVENTS_TABLE", "WebhookEvents")
QUEUE_URL = os.environ.get("EVENT_QUEUE_URL", "")
DEFAULT_WEBHOOK_URL = os.environ.get(
    "DEFAULT_WEBHOOK_URL", "https://httpbin.org/post"
)

# Lazy client loaders so unit tests run cleanly without AWS credentials
_dynamodb = None
_sqs = None


def get_dynamodb_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(TABLE_NAME)


def get_sqs_client():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs")
    return _sqs


def format_response(status_code: int, body: dict) -> dict:
    """Returns standard API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def validate_and_build_event(body: dict) -> dict:
    """Validates the incoming shopping order payload and builds canonical event."""
    if not isinstance(body, dict):
        raise ValueError("Request body must be a valid JSON object.")

    event_type = body.get("event_type")
    if event_type != "ORDER_CREATED":
        raise ValueError("Invalid or missing event_type. Expected 'ORDER_CREATED'.")

    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Missing or invalid 'payload' object.")

    order_id = payload.get("order_id")
    if not order_id or not isinstance(order_id, str):
        raise ValueError("Payload must contain a valid string 'order_id'.")

    product = payload.get("product")
    if not product or not isinstance(product, str):
        raise ValueError("Payload must contain a valid string 'product'.")

    quantity = payload.get("quantity")
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("Payload 'quantity' must be a positive integer (> 0).")

    total = payload.get("total")
    if not isinstance(total, (int, float)) or total <= 0:
        raise ValueError("Payload 'total' must be a positive number (> 0).")

    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    destination_url = body.get("destination_url", DEFAULT_WEBHOOK_URL)

    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "destination_url": destination_url,
        "payload": {
            "order_id": order_id,
            "product": product,
            "quantity": quantity,
            "total": total,
        },
    }


def ingest_event(body: dict) -> dict:
    """Saves initial state to DynamoDB and puts message into SQS."""
    event = validate_and_build_event(body)
    table = get_dynamodb_table()
    sqs = get_sqs_client()

    # 1. Store initial status as QUEUED
    table.put_item(
        Item={
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "timestamp": event["timestamp"],
            "destination_url": event["destination_url"],
            "payload": event["payload"],
            "status": "QUEUED",
            "attempts": 0,
            "last_error": None,
        }
    )

    # 2. Push message to SQS queue
    try:
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(event),
        )
    except Exception as exc:
        table.update_item(
            Key={"event_id": event["event_id"]},
            UpdateExpression="SET #s = :status, last_error = :err",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "INGESTION_FAILED",
                ":err": str(exc),
            },
        )
        raise RuntimeError(f"Failed to publish to SQS: {exc}")

    return {
        "event_id": event["event_id"],
        "status": "QUEUED",
        "message": "Order event accepted and queued for delivery",
    }


def get_event_status(event_id: str) -> dict:
    """Fetches event delivery status from DynamoDB."""
    table = get_dynamodb_table()
    response = table.get_item(Key={"event_id": event_id})
    return response.get("Item")


def lambda_handler(event, context):
    """Main routing handler for API Gateway."""
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod", "")
    ).upper()

    if method == "POST":
        try:
            raw_body = event.get("body") or "{}"
            if event.get("isBase64Encoded"):
                import base64
                raw_body = base64.b64decode(raw_body).decode("utf-8")

            body = json.loads(raw_body)
            result = ingest_event(body)
            return format_response(202, result)

        except (ValueError, json.JSONDecodeError) as err:
            return format_response(400, {"error": str(err)})
        except Exception as err:
            print(f"Error during ingestion: {err}")
            return format_response(500, {"error": "Internal server error"})

    elif method == "GET":
        path_params = event.get("pathParameters") or {}
        event_id = path_params.get("event_id")

        if not event_id:
            raw_path = event.get("rawPath") or event.get("path") or ""
            parts = [p for p in raw_path.strip("/").split("/") if p]
            if len(parts) >= 2 and parts[0] == "events":
                event_id = parts[1]

        if not event_id:
            return format_response(400, {"error": "Missing event_id in URL path."})

        item = get_event_status(event_id)
        if not item:
            return format_response(404, {"error": f"Event '{event_id}' not found."})

        return format_response(200, item)

    return format_response(405, {"error": f"Method {method} not allowed."})